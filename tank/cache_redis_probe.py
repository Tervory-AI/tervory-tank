"""Isolated real-Redis/pinned-LiteLLM proof; never imported by Tank serving."""
import asyncio
import hashlib
import importlib.metadata
import json
import multiprocessing
import os
import select
import socket
import socketserver
import tempfile
import threading
import time
from contextlib import asynccontextmanager
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Upstream(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path != '/v1/chat/completions' or body.get('model') != 'gpt-4o-mini':
            self.send_error(400)
            return
        with self.server.lock:
            self.server.calls += 1
            ident = self.server.calls
        answer = {'id':f'placeholder-local-{ident}','object':'chat.completion','created':1,
            'model':'gpt-4o-mini','choices':[{'index':0,'message':{'role':'assistant','content':'placeholder local answer'},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15,
                     'prompt_tokens_details':{'cached_tokens':0}}}
        raw = json.dumps(answer).encode()
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class Relay(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self,*args):
        self.stopped=False
        self.peers=set()
        self.lock=threading.Lock()
        super().__init__(*args)

    def stop(self):
        if self.stopped:
            return
        self.stopped=True
        self.shutdown()
        with self.lock:
            for peer in list(self.peers):
                try:
                    peer.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                peer.close()
        self.server_close()


class Forward(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            with socket.create_connection(('redis',6379),timeout=2) as upstream:
                peers = [self.request,upstream]
                with self.server.lock:
                    self.server.peers.update(peers)
                try:
                    while True:
                        ready,_,_ = select.select(peers,[],[],.2)
                        for source in ready:
                            data = source.recv(65536)
                            if not data:
                                return
                            (upstream if source is self.request else self.request).sendall(data)
                finally:
                    with self.server.lock:
                        self.server.peers.difference_update(peers)
        except (OSError,ValueError):
            return


def relay(port=0):
    server = Relay(('127.0.0.1',port),Forward)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    return server


@asynccontextmanager
async def gateway_session(port, upstream_port):
    import engine_config
    import httpx
    import yaml
    from litellm.proxy import proxy_server
    from litellm.proxy.auth.user_api_key_auth import UserAPIKeyAuth, user_api_key_auth
    deployed = yaml.safe_load(Path('/contract/source/config.yaml').read_text())
    settings = deployed['litellm_settings']
    config = {'model_list':[{'model_name':'placeholder-cache','litellm_params':{
        'model':'openai/gpt-4o-mini','api_base':f'http://127.0.0.1:{upstream_port}/v1',
        'api_key':'placeholder-no-provider-credential','input_cost_per_token':.000001,'output_cost_per_token':.000002},
        'model_info':{'id':'placeholder-stable-cache-deployment'}}],
        'litellm_settings':{'callbacks':settings['callbacks'],'cache':settings['cache'],
            'cache_params':{**settings['cache_params'],'host':'127.0.0.1','port':port}},
        'router_settings':{'num_retries':0},'general_settings':{}}
    config = engine_config.configure(config)
    assert config['litellm_settings']['cache'] is True
    with tempfile.TemporaryDirectory(prefix='redis-proof-') as folder:
        path = Path(folder)/'config.yaml'
        path.write_text(yaml.safe_dump(config))
        gateway,models,general = await proxy_server.proxy_config.load_config(router=None,config_file_path=str(path))
        proxy_server.llm_router,proxy_server.llm_model_list,proxy_server.general_settings = gateway,models,general
        async def identity():
            return UserAPIKeyAuth(api_key='placeholder',user_role='proxy_admin')
        proxy_server.app.dependency_overrides[user_api_key_auth] = identity
        import litellm
        observations=[]
        callback_types=[]
        for callback in litellm.callbacks:
            callback_types.append({'class':type(callback).__name__,
                'leaf_override':'async_post_call_response_headers_hook' in type(callback).__dict__})
            if type(callback).__name__!='TenantLangfuseCallback':
                continue
            original=callback.async_post_call_response_headers_hook
            async def observe(data,user_api_key_dict,response,request_headers=None,litellm_call_info=None,_original=original):
                hidden=getattr(response,'_hidden_params',{}) or {}
                info=litellm_call_info if isinstance(litellm_call_info,dict) else {}
                observations.append({'use_cache':(data.get('cache') or {}).get('use-cache'),
                    'hidden_cache_hit':hidden.get('cache_hit'),
                    'cache_field_names':[k for k in hidden if 'cache' in k],
                    'call_info_cache_hit':info.get('cache_hit')})
                return await _original(data,user_api_key_dict,response,request_headers,litellm_call_info)
            callback.async_post_call_response_headers_hook=observe
        async def complete(key):
            observations.clear()
            payload = {'model':'placeholder-cache','messages':[{'role':'user','content':'placeholder '+key}],
                'max_tokens':16,'stream':False,'fallbacks':[],'disable_fallbacks':True,
                'cache':{'use-cache':True,'ttl':900,'s-maxage':900,
                         'namespace':'tank:C1:v1:'+hashlib.sha256(key.encode()).hexdigest()}}
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=proxy_server.app),base_url='http://gateway',timeout=30) as client:
                response = await client.post('/v1/chat/completions',json=payload)
            result = {'status':response.status_code,'cache_layer':response.headers.get('x-tervory-cache-layer'),
                      'synthetic_cost_header':response.headers.get('x-litellm-response-cost'),
                      'native_cache_hit':response.headers.get('x-litellm-cache-hit'),'callback_observations':observations,'callback_types':callback_types,
                      'response_id':response.json().get('id'),'gateway_pid':os.getpid(),'version':importlib.metadata.version('litellm')}
            breaker=getattr(getattr(litellm.cache,'cache',None),'_circuit_breaker',None)
            result['redis_breaker']={'enabled':getattr(breaker,'enabled',False),
                'recovery_timeout':getattr(breaker,'recovery_timeout',0),'state':getattr(breaker,'_state',None)}
            return result
        # A fresh worker process owns the router; process exit closes clients.
        # Router.reset is not a production request step and can flush caches.
        yield complete


def cold_worker(port, upstream_port, key, output):
    try:
        async def once():
            async with gateway_session(port,upstream_port) as complete:
                return await complete(key)
        output.put({'result':asyncio.run(once())})
    except (OSError, RuntimeError, ValueError, ImportError, AssertionError) as error:
        output.put({'error_type':type(error).__name__})


def cold_request(port,upstream_port,key):
    context = multiprocessing.get_context('spawn')
    output = context.Queue()
    process = context.Process(target=cold_worker,args=(port,upstream_port,key,output))
    started = time.monotonic()
    process.start()
    try:
        process.join(70)
        if process.is_alive():
            raise TimeoutError('Cold gateway request exceeded 70 seconds')
        if process.exitcode or output.empty():
            raise RuntimeError('Cold gateway worker failed')
        result = output.get(timeout=1)
        if 'error_type' in result:
            raise RuntimeError('Cold gateway initialization/request failed: '+result['error_type'])
        return {**result['result'],'cold_process_elapsed_ms':(time.monotonic()-started)*1000}
    finally:
        if process.is_alive():
            process.kill()
        process.join()
        output.close()


def validate_case(result, *, hit, calls, expected_calls):
    assert result['status']==200, result
    assert result['version']=='1.106.4', result
    assert (result['cache_layer']=='C1') is hit, result
    assert calls==expected_calls, (calls,expected_calls,result)
    cost = Decimal(result['synthetic_cost_header'])
    assert (cost==0) if hit else (cost>0), result


def warm_worker(port,upstream_port,commands,output):
    async def loop():
        async with gateway_session(port,upstream_port) as complete:
            output.put({'ready':True})
            while True:
                key=await asyncio.to_thread(commands.get)
                if key is None:
                    return
                output.put({'result':await complete(key)})
    try:
        asyncio.run(loop())
    except (OSError, RuntimeError, ValueError, ImportError, AssertionError) as error:
        output.put({'error_type':type(error).__name__})


class WarmGateway:
    def __init__(self,port,upstream_port):
        context=multiprocessing.get_context('spawn')
        self.commands,self.output=context.Queue(),context.Queue()
        self.process=context.Process(target=warm_worker,args=(port,upstream_port,self.commands,self.output))
        self.process.start()
        if self.output.get(timeout=70).get('ready') is not True:
            self.close()
            raise RuntimeError('Persistent gateway initialization failed')

    def call(self,key):
        started=time.monotonic()
        self.commands.put(key)
        value=self.output.get(timeout=70)
        if 'result' not in value:
            raise RuntimeError('Persistent gateway request failed')
        return {**value['result'],'request_elapsed_ms':(time.monotonic()-started)*1000}

    def close(self):
        self.commands.put(None)
        self.process.join(3)
        if self.process.is_alive():
            self.process.kill()
        self.process.join()
        self.commands.close();self.output.close()


def recovery_delay(result):
    breaker=result['redis_breaker']
    seconds=breaker['recovery_timeout']
    if type(seconds) not in {int,float} or not 0<=seconds<=90:
        raise ValueError('SDK Redis recovery timeout exceeds isolated proof budget')
    return seconds+.5 if breaker['enabled'] else 0


def main():
    upstream = ThreadingHTTPServer(('127.0.0.1',0),Upstream)
    upstream.calls,upstream.lock = 0,threading.Lock()
    threading.Thread(target=upstream.serve_forever,daemon=True).start()
    connection = relay()
    port = connection.server_address[1]
    cases = []
    warm=None
    def check(name,key,hit,calls,*,persistent=False):
        result = (warm.call(key) if persistent else cold_request(port,upstream.server_address[1],key))
        validate_case(result,hit=hit,calls=upstream.calls,expected_calls=calls)
        cases.append({'case':name,**result,'stub_calls':upstream.calls,'persistent_gateway':persistent})
        print('CACHE_CASE='+json.dumps(cases[-1]),flush=True)
    try:
        check('initial_miss','a',False,1)
        check('cold_repeat_reuses_redis','a',True,1)
        warm=WarmGateway(port,upstream.server_address[1])
        check('warm_priming_miss','w',False,2,persistent=True)
        connection.stop()
        check('redis_unavailable_new_key_b','b',False,3,persistent=True)
        check('redis_unavailable_new_key_c','c',False,4,persistent=True)
        recovery_wait=recovery_delay(cases[-1])
        connection = relay(port)
        time.sleep(recovery_wait)
        check('warm_recovery_reads_existing_entry','a',True,4,persistent=True)
        check('warm_recovery_new_miss','d',False,5,persistent=True)
        check('cold_recovery_proves_redis_write','d',True,5)
        check('warm_recovery_repeat','d',True,5,persistent=True)
        pids={c['gateway_pid'] for c in cases if c['persistent_gateway']}
        assert len(pids)==1
        connection.stop()
        before=upstream.calls
        try:
            cold_result=cold_request(port,upstream.server_address[1],'cold-start')
            validate_case(cold_result,hit=False,calls=upstream.calls,expected_calls=before+1)
            cold_start={'outcome':'request-succeeded','result':cold_result,'stub_calls_delta':upstream.calls-before}
        except RuntimeError as error:
            cold_start={'outcome':'cold-worker-failed','detail':str(error),'stub_calls_delta':upstream.calls-before}
        print('CACHE_ACCEPTANCE_REPORT='+json.dumps({'passed':True,'scope':'isolated-pinned-image-and-source-equivalence',
            'production_outage_proof':False,'paid_provider_calls':0,'real_dollar_savings':None,
            'fixture_ttl_seconds':900,'price_evidence':'synthetic local fixture rates only','fault':'closed local Redis relay and active connections; disposable Redis retains data',
            'cold_gateway_backend_verification':True,'same_gateway_process_outage_and_recovery':True,
            'recovery_wait_seconds':recovery_wait,'cold_start_with_redis_unavailable':cold_start,'cases':cases}),flush=True)
    finally:
        if warm is not None:
            warm.close()
        connection.stop()
        upstream.shutdown();upstream.server_close()


if __name__=='__main__':
    main()
