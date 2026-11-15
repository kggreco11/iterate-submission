import base64
import pytest
pytest.importorskip("cryptography")
import sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes


@pytest.mark.parametrize('swarm', [False, True])
def test_launch_never_sends_plaintext_key(tmp_path, monkeypatch, swarm):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
    import launch_openai_vm as launch
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nums = private.public_key().public_numbers()
    b64 = lambda x: base64.b64encode(x.to_bytes((x.bit_length()+7)//8, 'big')).decode()
    xml = f'<RSAKeyValue><Modulus>{b64(nums.n)}</Modulus><Exponent>{b64(nums.e)}</Exponent></RSAKeyValue>'
    pilot = tmp_path / 'pilot'; pilot.mkdir(); (pilot / 'summary.json').write_text('{}')
    env = tmp_path / 'env'; sentinel = 'test-secret-do-not-transmit-plaintext'; env.write_text('OPENAI_API_KEY='+sentinel+'\nPAST_API_KEY=past-test-sentinel')
    captured = {}
    def invoke(script, log, stage, **kw):
        assert sentinel not in script and 'past-test-sentinel' not in script
        captured[stage] = script
        return xml if stage == 'prepare_credential_destination' else 'ok'
    monkeypatch.setattr(launch, 'invoke', invoke)
    monkeypatch.setattr(launch, 'bundle', lambda: b'source')
    monkeypatch.setattr(sys, 'argv', ['launch', '--pilot-dir', str(pilot), '--source-env', str(env), '--out', str(tmp_path/'out'), '--run-id', 'unit'] + (['--swarm'] if swarm else []))
    launch.main()
    import re
    encrypted = re.search("FromBase64String\\('([^']+)'\\)", captured['provision_credential']).group(1)
    plain = private.decrypt(base64.b64decode(encrypted), padding.OAEP(mgf=padding.MGF1(hashes.SHA1()),algorithm=hashes.SHA1(),label=None))
    assert plain.decode() == 'OPENAI_API_KEY='+sentinel+('\nPAST_API_KEY=past-test-sentinel' if swarm else '')
    assert 'finally' in captured['provision_credential']
    assert 'inheritance:r' in captured['prepare_credential_destination']
    assert set(captured) == {'prepare_credential_destination','provision_credential','deploy','launch'}
