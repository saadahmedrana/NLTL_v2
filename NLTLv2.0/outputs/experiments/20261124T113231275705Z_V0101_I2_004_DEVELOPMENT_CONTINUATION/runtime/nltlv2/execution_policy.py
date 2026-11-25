"""Conservative failure attribution; unknown failures never become code accusations."""
from pyparsing import ParseBaseException
from pyshacl.errors import ValidationFailure,ConstraintLoadError,ShapeLoadError
CANDIDATE_MESSAGES=(
 'All potentially pre-bound variables must be selected',
 "Using 'SELECT *' in a nested SELECT",
 'Cannot use AS to re-bind potentially pre-bound',
 'A SPARQL Constraint must not contain',
 'Ill-formed nested SELECT',
)
def classify(error):
 text=str(error)
 if isinstance(error,(TimeoutError,MemoryError,RecursionError)) or any(x in text.lower() for x in ['timed out','resource limit','out of memory']):return 'RESOURCE_UNCERTAIN'
 if isinstance(error,(ConstraintLoadError,ShapeLoadError,ParseBaseException)):return 'CANDIDATE_ERROR'
 if any(x in text for x in CANDIDATE_MESSAGES) and isinstance(error,(ValidationFailure,RuntimeError)):return 'CANDIDATE_ERROR'
 return 'INFRASTRUCTURE_OR_UNKNOWN'
def diagnostic(error):return type(error).__name__+': '+str(error)
