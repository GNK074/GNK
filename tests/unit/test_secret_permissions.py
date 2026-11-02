import importlib.util,os,stat
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('secret_permissions',ROOT/'infrastructure/env/secret_permissions.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def fixture_config(root):
    directory=root/'secrets';directory.mkdir()
    config={'secrets':{}}
    for name in module.NAMES:
        path=directory/name;path.write_bytes(('test-only-'+name).encode());path.chmod(0o600)
        config['secrets'][name]={'file':str(path)}
    return config

def test_repair_preserves_all_secret_values_and_limits_directory_access(tmp_path):
    config=fixture_config(tmp_path)
    before={p.name:p.read_bytes() for p in (tmp_path/'secrets').iterdir()}
    assert module.apply_permissions(tmp_path,config,apply=True)
    assert before=={p.name:p.read_bytes() for p in (tmp_path/'secrets').iterdir()}
    if os.name=='posix':
        assert stat.S_IMODE((tmp_path/'secrets').stat().st_mode)==0o700
        assert all(stat.S_IMODE(p.stat().st_mode)==0o444 for p in (tmp_path/'secrets').iterdir())
        assert module.apply_permissions(tmp_path,config)==[]

def test_external_file_is_rejected_before_any_permissions_change(tmp_path):
    config=fixture_config(tmp_path);outside=tmp_path/'external';outside.write_text('do-not-change')
    config['secrets']['redis_password']['file']=str(outside)
    before={p.name:p.stat().st_mode for p in (tmp_path/'secrets').iterdir()}
    with pytest.raises(ValueError):module.apply_permissions(tmp_path,config,apply=True)
    assert before=={p.name:p.stat().st_mode for p in (tmp_path/'secrets').iterdir()}
    assert outside.read_text()=='do-not-change'

def test_missing_file_is_rejected_without_regenerating_it(tmp_path):
    config=fixture_config(tmp_path);path=tmp_path/'secrets/app_db_password';path.unlink()
    with pytest.raises(ValueError):module.apply_permissions(tmp_path,config,apply=True)
    assert not path.exists()
