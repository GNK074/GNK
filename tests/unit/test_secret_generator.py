import importlib.util,sys
from pathlib import Path
import pytest

def test_secret_generator_never_overwrites_and_never_prints_values(tmp_path,monkeypatch,capsys):
    root=Path(__file__).resolve().parents[2]
    spec=importlib.util.spec_from_file_location('gnk_generator',root/'infrastructure/env/generate_secrets.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'ROOT',tmp_path)
    (tmp_path/'.env.production.example').write_text((root/'.env.production.example').read_text())
    monkeypatch.setattr(sys,'argv',['generate','--production','--output','.env.generated'])
    module.main()
    content=(tmp_path/'.env.generated').read_text()
    assert 'GENERATE_WITH' not in content
    assert len(list((tmp_path/'secrets').iterdir()))==3
    stdout=capsys.readouterr().out
    for path in (tmp_path/'secrets').iterdir():assert path.read_text().strip() not in stdout
    before={p.name:p.read_bytes() for p in (tmp_path/'secrets').iterdir()}
    with pytest.raises(SystemExit):module.main()
    assert before=={p.name:p.read_bytes() for p in (tmp_path/'secrets').iterdir()}
    # A new output name still cannot rotate an existing database/encryption profile.
    monkeypatch.setattr(sys,'argv',['generate','--production','--output','.env.another'])
    with pytest.raises(SystemExit):module.main()
    assert not (tmp_path/'.env.another').exists()
