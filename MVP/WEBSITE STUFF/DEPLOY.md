# Deploy NLTL to Aalto vhosts

From your **Mac** terminal, in the folder containing this package:

```bash
scp -r NLTL_Aalto_Website_R13/* ranas2@webfiles.aalto.fi:/l/data/natural-language-to-logic.aalto.fi/
```

Note: this command overwrites the existing test `index.html`. It does not remove other remote files.

Check:

```bash
curl -I https://natural-language-to-logic.aalto.fi/
curl -I https://natural-language-to-logic.aalto.fi/vocab/
curl -I https://natural-language-to-logic.aalto.fi/vocab/nltl_benchmark_vocabulary.ttl
curl -I https://natural-language-to-logic.aalto.fi/vocab/nltl_benchmark_vocabulary.rdf
curl -I https://natural-language-to-logic.aalto.fi/context/nltl_benchmark_context.jsonld
```

Check Content-Type headers. Aalto may need to configure MIME types for `.ttl`, `.rdf` and `.jsonld`. Do not submit the w3id PR until all intended destination URLs work.

**Important:** This is a static hosting package, not a complete w3id content-negotiation configuration. Ontology identifier `https://w3id.org/nltl/vocab` and hash-term IRIs need a carefully tested redirect to the vocabulary resource, not merely the HTML index. Keep locked R13 files unchanged.
