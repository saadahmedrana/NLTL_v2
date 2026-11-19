"""Source-backed finite-set coverage proof. No evaluation fixtures or labels are read.

Supported encodings: sh:in; sh:node indirection; value-focus sh:or/and of
finite sets, including sh:hasValue singleton NodeShapes. Owner-focus and/or
are interpreted separately so a bypass branch cannot certify coverage.
SPARQL, xone, not, qualified constraints and unsupported paths stay unresolved.
This proves only the declared finite-set obligation, not whole-shape correctness.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import FrozenSet

from rdflib import BNode, Graph, Literal, RDF, URIRef
from rdflib.namespace import SH, RDFS, XSD

from .core import finding


@dataclass(frozen=True)
class Domain:
    # finite = exact membership set; open = no closed-set enforcement;
    # unknown = unsupported equivalence/applicability. Never credit unknown.
    kind: str
    values: FrozenSet = frozenset()
    notes: tuple[str, ...] = ()


def combine(domains, operator):
    domains = list(domains)
    if not domains:
        return Domain('open' if operator == 'and' else 'finite')
    notes = tuple(note for d in domains for note in d.notes)
    if any(d.kind == 'unknown' for d in domains):
        return Domain('unknown', notes=notes)
    if operator == 'or':
        if any(d.kind == 'open' for d in domains):
            return Domain('open', notes=notes + ('A logical alternative permits values without the closed-set constraint.',))
        return Domain('finite', frozenset().union(*(d.values for d in domains)), notes)
    finite = [d.values for d in domains if d.kind == 'finite']
    return Domain('finite', frozenset.intersection(*finite), notes) if finite else Domain('open', notes=notes)


def rdf_list(graph, head):
    """Reject malformed/cyclic/multiply linked RDF lists instead of guessing."""
    result, seen = [], set()
    while head != RDF.nil:
        if head in seen:
            raise ValueError('Cyclic RDF list')
        seen.add(head)
        first, rest = list(graph.objects(head, RDF.first)), list(graph.objects(head, RDF.rest))
        if len(first) != 1 or len(rest) != 1:
            raise ValueError('Malformed RDF list')
        result.append(first[0])
        head = rest[0]
    return result


class Coverage:
    def __init__(self, graph, schema, obligation):
        self.g, self.schema, self.obligation = graph, schema, obligation
        self.path = tuple(obligation['path'])
        self.target = URIRef(obligation['target_class'])
        self.encodings = []
        self.misplaced = []

    def sequence(self, node):
        if isinstance(node, URIRef):
            return (str(node),)
        if (node, RDF.first, None) in self.g:
            seq = rdf_list(self.g, node)
            if not seq or any(not isinstance(x, URIRef) for x in seq):
                return None
            return tuple(map(str, seq))
        return None

    def active(self, node):
        values = list(self.g.objects(node, SH.deactivated))
        if len(values) > 1:
            raise ValueError('Multiple sh:deactivated values')
        if values and (not isinstance(values[0], Literal) or values[0].datatype != XSD.boolean or not isinstance(values[0].toPython(), bool)):
            raise ValueError('Invalid sh:deactivated value; applicability is unresolved')
        return not values or values[0] != Literal(True)

    def domain(self, node, remaining, stack=(), conditional=False):
        if node in stack:
            return Domain('unknown', notes=('Recursive shape reference.',))
        if not self.active(node):
            return Domain('open', notes=('Deactivated shape does not enforce the obligation.',))
        stack = stack + (node,)
        parts = []
        unsupported = [SH.sparql, SH.js, SH['not'], SH.xone, SH.qualifiedValueShape,
                       SH.equals, SH.disjoint, SH.lessThan, SH.lessThanOrEquals,
                       SH.closed, SH.pattern, SH.uniqueLang, SH.minLength, SH.maxLength,
                       SH.minInclusive, SH.maxInclusive, SH.minExclusive, SH.maxExclusive,
                       SH.languageIn, SH.rule]
        custom_parameters={self.g.value(parameter, SH.path) for component in self.g.subjects(RDF.type, SH.ConstraintComponent) for parameter in self.g.objects(component, SH.parameter)}
        if any((node, p, None) in self.g for p in custom_parameters if p is not None):
            parts.append(Domain('unknown', notes=('Custom constraint-component equivalence is unsupported.',)))
        if any((node, p, None) in self.g for p in unsupported):
            parts.append(Domain('unknown', notes=('Unsupported constraint can affect equivalence or applicability.',)))
        if not remaining:
            for head in self.g.objects(node, SH['in']):
                members = rdf_list(self.g, head)
                self.encodings.append('sh:in at value focus')
                parts.append(Domain('finite', frozenset(members)))
            # On a value-focus NodeShape (not a property shape), hasValue is a singleton set.
            if (node, SH.path, None) not in self.g:
                for value in self.g.objects(node, SH.hasValue):
                    self.encodings.append('value-focus sh:hasValue singleton')
                    parts.append(Domain('finite', frozenset([value])))
            elif (node, SH.hasValue, None) in self.g:
                # A PropertyShape hasValue is existential, not universal membership.
                parts.append(Domain('unknown', notes=('Property-shape sh:hasValue does not by itself close all values.',)))
        elif any((node, p, None) in self.g for p in [SH['in'], SH.hasValue, SH.datatype]):
            # These constrain the ship identity, not its iceClass property.
            parts.append(Domain('unknown', notes=('Owner identity constraint is not an iceClass value constraint.',)))

        # Type/range/IRI checks are deliberately not finite-set evidence. At owner
        # focus a non-guaranteed class guard makes conditional applicability unknown.
        if not remaining:
            expected = [URIRef(x['iri']) for x in self.obligation['members']]
            for cls in self.g.objects(node, SH['class']):
                if not all(any(self.schema.subtype(t, cls) for t in self.schema.graph.objects(value, RDF.type)) for value in expected):
                    parts.append(Domain('unknown', notes=('Value class constraint is not proved compatible with all six canonical members.',)))
            if (node, SH.datatype, None) in self.g:
                parts.append(Domain('finite', frozenset(), notes=('A literal sh:datatype cannot admit any of the six required IRI values; term-kind correction is required.',)))
        if not remaining and any(kind in [SH.Literal, SH.BlankNode, SH.BlankNodeOrLiteral] for kind in self.g.objects(node, SH.nodeKind)):
            parts.append(Domain('finite', frozenset(), notes=('Node kind excludes all six canonical IRI members.',)))
        if remaining:
            for cls in self.g.objects(node, SH['class']):
                if not self.schema.subtype(self.target, cls):
                    parts.append(Domain('unknown', notes=('Owner class guard is not guaranteed for every required ship.',)))

        for ps in self.g.objects(node, SH.property):
            if not self.active(ps):
                continue
            paths = list(self.g.objects(ps, SH.path))
            if len(paths) != 1:
                parts.append(Domain('unknown', notes=('Missing/multiple property paths.',)))
                continue
            seq = self.sequence(paths[0])
            if seq is None:
                parts.append(Domain('unknown', notes=('Unsupported property-path encoding.',)))
            elif remaining and tuple(remaining[:len(seq)]) == seq:
                parts.append(self.domain(ps, remaining[len(seq):], stack, conditional))
            else:
                if conditional and remaining:
                    parts.append(Domain('unknown', notes=('Owner alternative has an unproven additional property/applicability guard.',)))
                if self.contains_membership(ps):
                    self.misplaced.append({'path': list(seq), 'remaining_required_path': list(remaining)})
                # Explicit other paths do not establish coverage at the required path.
                # A relational or otherwise opaque cross-path proof remains unknown.
                if self.contains_opaque(ps):
                    parts.append(Domain('unknown', notes=('Unsupported cross-path constraint.',)))

        for child in self.g.objects(node, SH.node):
            if (child, SH.path, None) in self.g:
                parts.append(Domain('unknown', notes=('sh:node referencing a PropertyShape has unsupported focus semantics.',)))
            else:
                self.encodings.append('sh:node indirection')
                parts.append(self.domain(child, remaining, stack, conditional))
        for predicate, operator in [(SH['and'], 'and'), (SH['or'], 'or')]:
            for head in self.g.objects(node, predicate):
                children = rdf_list(self.g, head)
                self.encodings.append('sh:' + operator + (' at owner focus' if remaining else ' at value focus'))
                domains = [self.domain(child, remaining, stack, conditional or bool(remaining and operator == 'or')) for child in children]
                if remaining and operator == 'or' and domains and all(d.kind == 'finite' for d in domains):
                    union = frozenset().union(*(d.values for d in domains))
                    # OR of universal property restrictions is not the universal OR
                    # of value restrictions. Never assume unsupported maxCount=1.
                    if any(d.values == union for d in domains):
                        parts.append(Domain('finite', union))
                    else:
                        parts.append(Domain('unknown', notes=('Owner-level OR splits value sets; mixed allowed assignments are not proven without an unsupported cardinality assumption.',)))
                else:
                    parts.append(combine(domains, operator))
        return combine(parts, 'and')

    def contains_membership(self, node, seen=None):
        seen = set() if seen is None else seen
        if node in seen:
            return False
        seen.add(node)
        if (node, SH['in'], None) in self.g:
            return True
        for p in [SH.node, SH.property]:
            if any(self.contains_membership(x, seen) for x in self.g.objects(node, p)):
                return True
        for p in [SH['or'], SH['and']]:
            if any(self.contains_membership(x, seen) for h in self.g.objects(node, p) for x in rdf_list(self.g, h)):
                return True
        return False

    def contains_opaque(self, node, seen=None):
        seen = set() if seen is None else seen
        if node in seen:
            return True
        seen.add(node)
        if any((node, p, None) in self.g for p in [SH.sparql, SH['not'], SH.xone, SH.equals, SH.disjoint, SH.qualifiedValueShape]):
            return True
        if any(self.contains_opaque(x, seen.copy()) for p in [SH.node, SH.property] for x in self.g.objects(node, p)):
            return True
        return any(self.contains_opaque(x, seen.copy()) for p in [SH['or'], SH['and']] for h in self.g.objects(node, p) for x in rdf_list(self.g, h))

    def prove(self):
        roots, wrong_targets, unsupported_targets = [], [], []
        for root in set(self.g.subjects(SH.targetClass, None)):
            if not self.active(root):
                continue
            classes = list(self.g.objects(root, SH.targetClass))
            if any(self.schema.subtype(self.target, cls) for cls in classes):
                roots.append(root)
            else:
                wrong_targets.append({'target_classes': list(map(str, classes))})
        # Other target strategies need an explicit equivalence proof; never guess.
        for p in [SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf, SH.target]:
            unsupported_targets += [str(p) for s in self.g.subjects(p, None) if self.active(s)]
        domain = combine([self.domain(root, self.path) for root in roots], 'and')
        if unsupported_targets:
            domain = Domain('unknown', notes=domain.notes + ('Unsupported target strategy: ' + ', '.join(unsupported_targets),))
        if not roots and self.g.value(None, SH.sparql) is not None:
            domain = Domain('unknown', notes=('SPARQL/applicability equivalence is not established.',))
        expected = frozenset(URIRef(x['iri']) for x in self.obligation['members'])
        status = ('UNRESOLVED_EQUIVALENCE' if domain.kind == 'unknown' else
                  'MISSING_ENUMERATION' if domain.kind == 'open' else
                  'COVERED' if domain.values == expected else 'INCORRECT_ENUMERATION_SET')
        if domain.kind == 'open' and (self.misplaced or wrong_targets):
            status = 'WRONG_PATH_OR_APPLICABILITY'
        return dict(obligation_id=self.obligation['id'],status=status,
                    required_target=str(self.target),required_path=list(self.path),
                    expected_IRIs=sorted(map(str, expected)),
                    effective_members=sorted(x.n3() for x in domain.values) if domain.kind == 'finite' else None,
                    missing_IRIs=sorted(str(x) for x in expected - domain.values) if domain.kind == 'finite' else [],
                    extra_terms=sorted(x.n3() for x in domain.values - expected) if domain.kind == 'finite' else [],
                    membership_domain=domain.kind,recognized_encodings=sorted(set(self.encodings)),
                    misplaced=self.misplaced,wrong_targets=wrong_targets,notes=list(domain.notes),
                    source_clause=self.obligation['source']['clause'],
                    cardinality='Separate: maxCount 1 has no established source/explicit-contract support.')


# A bounded lexical scanner is used only for source locations, never proof of SHACL meaning.
TOKEN = re.compile(r'''\s+|\#[^\n]*|<[^>]*>|"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[\[\]();.,]|[^\s\[\]();,]+''')


def source_location(code, required_path):
    prefixes = dict(re.findall(r'(?i)(?:@prefix|PREFIX)\s+([\w-]+):\s*<([^>]+)>', code))
    def expanded(token):
        if token.startswith('<'):
            return token[1:-1]
        prefix, sep, local = token.partition(':')
        return prefixes.get(prefix, '') + local if sep else token
    tokens = [m for m in TOKEN.finditer(code) if not m.group().isspace() and not m.group().startswith('#')]
    position = None
    for i, tok in enumerate(tokens[:-1]):
        if expanded(tok.group()) == str(SH.path) and expanded(tokens[i+1].group()) == required_path[-1]:
            position = tok.start()
            break
    if position is None:
        position = next((m.start() for m in tokens if expanded(m.group()) in [str(SH['in']), str(SH.targetClass)]), 0)
    stack, spans = [], []
    for tok in tokens:
        if tok.group() == '[':
            stack.append(tok.start())
        elif tok.group() == ']' and stack:
            spans.append((stack.pop(), tok.end()))
    enclosing = [(a,b) for a,b in spans if a <= position < b]
    if enclosing:
        begin, end = min(enclosing, key=lambda pair: pair[1]-pair[0])
    else:
        begin, end = code.rfind('\n', 0, position)+1, code.find('\n', position)
        if end < 0:
            end = len(code)
    line = code.count('\n', 0, begin)+1
    last = code.count('\n', 0, end)+1
    return f'candidate lines {line}-{last}, offsets {begin}:{end}; required path '+ ' / '.join(required_path), code[begin:end]


def coverage_findings(candidate, schema, requirement_id, graph=None):
    obligations = schema.enumeration_obligations.get(requirement_id, [])
    if not obligations:
        return [], []
    graph = graph or Graph().parse(data=candidate.code, format='turtle')
    findings, reports = [], []
    for obligation in obligations:
        try:
            report = Coverage(graph, schema, obligation).prove()
        except (ValueError, RecursionError, TypeError) as e:
            report = dict(obligation_id=obligation['id'],status='UNRESOLVED_EQUIVALENCE',reason=str(e),expected_IRIs=[x['iri'] for x in obligation['members']],required_path=obligation['path'],source_clause=obligation['source']['clause'])
        reports.append(report)
        if report['status'] == 'COVERED':
            continue
        unresolved = report['status'] == 'UNRESOLVED_EQUIVALENCE'
        category = 'UNRESOLVED_CONTEXT' if unresolved else ('PATH_CONTRACT_ERROR' if report['status']=='WRONG_PATH_OR_APPLICABILITY' else 'SOURCE_BACKED_LOGIC_ERROR')
        location, excerpt = source_location(candidate.code, obligation['path'])
        diagnostic = json.dumps(report, indent=2, ensure_ascii=False)
        if unresolved:
            message = 'Enumeration equivalence/applicability cannot be established.'
        elif report['status'] == 'INCORRECT_ENUMERATION_SET':
            message = 'Closed-set members differ from the source: missing permitted IRIs '+json.dumps(report['missing_IRIs'])+'; extra allowed terms '+json.dumps(report['extra_terms'])+'.'
        else:
            message = 'Closed-set obligation '+report['status']+': current type/range/IRI checks or misplaced restrictions permit unlisted values at the required path/applicability; no verified closed-set enforcement is present.'
        suggestion = ('Provide an evidenced equivalent encoding in the documented supported subset; do not invent an encoding or treat this as a confirmed code defect.' if unresolved else
                      'At applicable '+obligation['target_class']+' nodes, constrain every value at '+ ' / '.join(obligation['path'])+' with sh:in containing exactly the six expected IRIs, or a documented equivalent. An incomplete list rejects permitted classes; an extra member permits an unlisted value. Preserve unrelated obligations, targets and applicability. Do not add maxCount 1: its support is unresolved.')
        evidence = json.dumps(dict(obligation_id=obligation['id'],source=obligation['source'],owner=obligation['owner_evidence'],controlled_value_bindings=obligation['members'],cardinality_review=obligation['cardinality_review']), ensure_ascii=False)
        findings.append(finding(candidate,category,message,excerpt=excerpt,expected=json.dumps(dict(target=obligation['target_class'],path=obligation['path'],six_IRIs=report['expected_IRIs'])),evidence=evidence,suggestion=suggestion,location=location,confirmed=not unresolved,diagnostic=diagnostic))
    return findings, reports
