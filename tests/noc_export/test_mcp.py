"""用本机虚构 MCP 服务验证实际 stdio 协议和输出解析。"""
import importlib.util
from pathlib import Path
import shlex
import sys

import pytest

SPEC = importlib.util.spec_from_file_location('noc_export_mcp', Path(__file__).parents[2] / 'scripts/noc_export/exporter.py')
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


def test_stdio_mcp_notifications_json_and_original_error(tmp_path):
    fake = tmp_path / 'fake_mcp.py'
    fake.write_text('''import json,sys
for line in sys.stdin:
 p=json.loads(line)
 if 'id' not in p: continue
 if p['method']=='initialize': r={'protocolVersion':'2024-11-05','capabilities':{},'serverInfo':{'name':'fake','version':'0'}}
 elif p['params']['arguments']['function']=='bad': r={'isError':True,'content':[{'type':'text','text':'### Error\\nFAKE connection refused'}]}
 else: r={'content':[{'type':'text','text':'### Result\\n{"status":"done","count":2}\\n### Ran Playwright code\\nexample'}]}
 print(json.dumps({'jsonrpc':'2.0','id':p['id'],'result':r}),flush=True)
''')
    client = exporter.McpClient(shlex.quote(sys.executable)+' '+shlex.quote(str(fake)), tmp_path)
    try:
        assert client.evaluate('fake') == {'status':'done','count':2}
        with pytest.raises(RuntimeError, match='FAKE connection refused'):
            client.evaluate('bad')
    finally:
        client.close()
    assert client.proc.poll() is not None
