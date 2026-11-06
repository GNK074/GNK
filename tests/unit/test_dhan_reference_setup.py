import importlib.util,json,os,stat
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('reference_setup',ROOT/'infrastructure/env/configure_dhan_reference.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_pending_reference_repairs_only_missing_setting(tmp_path,capsys):
 env=tmp_path/'.env'
 original='TRADING_ENABLED=true\nLIVE_TRADING_ENABLED=true\nDHAN_EXECUTION_ENABLED=true\nDHAN_TICK_SIZE_MULTIPLIER=0.01\nDHAN_STREAM_ENABLED=true\nSMTP_PASSWORD="private-fixture"\n'
 env.write_text(original,encoding='utf-8');env.chmod(0o600)
 reference=module.configure(tmp_path)
 assert env.read_text(encoding='utf-8')==original+'DHAN_EXECUTION_REFERENCE='+reference+'\n'
 record=json.loads((tmp_path/'deploy/review_records'/(reference+'.json')).read_text(encoding='utf-8'))
 assert record['status']=='PENDING' and not record['broker_approved'] and not record['review_completed']
 assert record['reference']==reference and 'private-fixture' not in capsys.readouterr().out
 if os.name!='nt':assert stat.S_IMODE(env.stat().st_mode)==0o600

def test_existing_reference_is_never_overwritten(tmp_path):
 env=tmp_path/'.env';text="DHAN_EXECUTION_REFERENCE='existing-case' # retained\nTRADING_ENABLED=true\n"
 env.write_text(text,encoding='utf-8')
 assert module.configure(tmp_path) is None
 assert env.read_text(encoding='utf-8')==text and not (tmp_path/'deploy/review_records').exists()

def test_invalid_duplicate_references_are_normalized(tmp_path):
 env=tmp_path/'.env';env.write_text('DHAN_EXECUTION_REFERENCE=false\nKEEP=this\nexport DHAN_EXECUTION_REFERENCE="pending" # old\n',encoding='utf-8')
 reference=module.configure(tmp_path);text=env.read_text(encoding='utf-8')
 assert text.count('DHAN_EXECUTION_REFERENCE=')==1 and 'KEEP=this\n' in text
 assert module.configure(tmp_path) is None
 assert len(list((tmp_path/'deploy/review_records').glob('*.json')))==1

def test_missing_environment_is_not_created(tmp_path):
 with pytest.raises(ValueError):module.configure(tmp_path)
 assert not (tmp_path/'.env').exists()
