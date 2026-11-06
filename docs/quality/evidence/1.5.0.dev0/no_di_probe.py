import asyncio,json,time,random
from importlib.metadata import version
from tachyon_api import Tachyon,Query
app=Tachyon()
@app.get('/plain')
async def plain():return {'ok':True}
@app.get('/query')
async def query(n:int=Query(2)):return n
async def receive():return {'type':'http.request','body':b'','more_body':False}
async def run():
    rows=[];rng=random.Random(42)
    for case in ['/plain','/query']:
        expected=b'{"ok":true}' if case=='/plain' else b'2'
        template={'type':'http','method':'GET','path':case,'root_path':'','query_string':b'n=2','headers':[],'http_version':'1.1','scheme':'http','asgi':{'version':'3.0'}}
        async def send(message):
            if message['type']=='http.response.body':assert message['body']==expected
        for _ in range(5000):await app(dict(template),receive,send)
    for repeat in range(15):
        cases=['/plain','/query'];rng.shuffle(cases)
        for case in cases:
            expected=b'{"ok":true}' if case=='/plain' else b'2'
            template={'type':'http','method':'GET','path':case,'root_path':'','query_string':b'n=2','headers':[],'http_version':'1.1','scheme':'http','asgi':{'version':'3.0'}}
            async def send(message):
                if message['type']=='http.response.body':assert message['body']==expected
            cpu=time.process_time_ns();wall=time.perf_counter_ns()
            for _ in range(20000):await app(dict(template),receive,send)
            rows.append({'repeat':repeat,'case':case,'wall_ns_per_request':(time.perf_counter_ns()-wall)/20000,'cpu_ns_per_request':(time.process_time_ns()-cpu)/20000})
    print(json.dumps({'version':version('tachyon-api'),'origin':__import__('tachyon_api').__file__,'python':__import__('sys').version,'dependencies':{p:version(p) for p in ['starlette','anyio','msgspec','orjson','uvicorn']},'rows':rows}))
asyncio.run(run())
