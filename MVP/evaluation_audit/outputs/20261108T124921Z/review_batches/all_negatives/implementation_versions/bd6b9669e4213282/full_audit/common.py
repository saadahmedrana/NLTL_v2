from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import audit
BASE=audit.HERE/'outputs/20261108T124921Z'
OUT=BASE/'review_batches/all_negatives'
OLD=BASE/'review_batches/batch50'
SCRIPTS=audit.BENCH/'scripts'
SOURCE_FILES={'I2':'IACS_I2_full.txt','IMO':'IMO_full.txt','TRF':'TRAFICOM_full.txt','IMO26':'IMO26_full.txt'}

def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');audit.dump(tmp,value);tmp.replace(path)
