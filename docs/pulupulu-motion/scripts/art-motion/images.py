#!/usr/bin/env python3
"""图片接入：选择当前宿主工具、生成调用计划、验收并收纳素材。不代替Agent调用工具。"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

import capabilities as c


def perform_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def perform_inspect_image(path):
    try:
        from PIL import Image
    except ImportError:
        raise c.ConfigError('图片验收需要Pillow；状态探查不需要。请按环境安装依赖') from None
    try:
        payload_value=Path(path).read_bytes()
        with Image.open(io.BytesIO(payload_value)) as layer_image:
            output_format=layer_image.format
            if output_format not in ('PNG','JPEG','WEBP'):
                raise c.ConfigError('支持PNG/JPEG/WEBP静态素材')
            if getattr(layer_image,'n_frames',1)!=1:
                raise c.ConfigError('多帧图片请先明确选帧，不隐式截取')
            layer_image.verify()
        with Image.open(io.BytesIO(payload_value)) as layer_image:
            layer_image.load()
            opacity_value=layer_image.convert('RGBA').getchannel('A').getextrema()
            return {'width':layer_image.width,'height':layer_image.height,'format':output_format.lower(),
                    'has_transparency':opacity_value[0]<255,'has_visible_pixels':opacity_value[1]>0,'sha256':hashlib.sha256(payload_value).hexdigest()}
    except c.ConfigError:raise
    except Exception as caught_error:
        raise c.ConfigError('图片无法完整解码：'+type(caught_error).__name__) from None


def perform_runtime_tools(path, session):
    raw_payload=c.read_json(Path(path))
    if raw_payload.get('session_id')!=session or not session:
        raise c.ConfigError('宿主能力快照不属于本次会话')
    if raw_payload.get('host') not in ('codex','claude-code','kimi','other'):
        raise c.ConfigError('未知宿主；可使用other但须提供真实工具声明')
    observed_value=raw_payload.get('observed_at')
    if not isinstance(observed_value,(int,float)) or not 0<=time.time()-observed_value<=900:
        raise c.ConfigError('工具快照已过期，请从当前会话重新取得（15分钟内）')
    tools=raw_payload.get('tools')
    if not isinstance(tools,list):raise c.ConfigError('工具快照需要tools列表；不可用时显式给空列表')
    id_entries=set()
    for tool in tools:
        if not isinstance(tool,dict) or not isinstance(tool.get('id'),str) or not tool['id'].strip() or tool['id'] in id_entries:
            raise c.ConfigError('工具ID缺失或重复')
        id_entries.add(tool['id'])
        if tool.get('kind') not in ('host','mcp') or tool.get('cost') not in ('subscription','paid_api','unknown','none') or tool.get('network') not in ('cloud','local'):
            raise c.ConfigError('工具必须声明执行来源、计费类型和网络范围')
        if not isinstance(tool.get('operations'),list) or not tool['operations'] or any(sample_value not in ('generate','edit') for sample_value in tool['operations']):
            raise c.ConfigError('工具操作声明无效')
        for lookup_key in ('reference_images','transparent_background'):
            if not isinstance(tool.get(lookup_key),bool):raise c.ConfigError('缺少工具特性：'+lookup_key)
    return raw_payload


def perform_request_data(path):
    raw_payload=c.read_json(Path(path))
    if set(raw_payload)-{'prompt','operation','references','transparent_background','min_width','min_height'}:
        raise c.ConfigError('图片需求包含不支持字段')
    if not isinstance(raw_payload.get('prompt'),str) or not raw_payload['prompt'].strip():
        raise c.ConfigError('需要非空图片描述')
    raw_payload.setdefault('operation','generate');raw_payload.setdefault('references',[])
    raw_payload.setdefault('transparent_background',False);raw_payload.setdefault('min_width',1);raw_payload.setdefault('min_height',1)
    if raw_payload['operation'] not in ('generate','edit') or not isinstance(raw_payload['references'],list) or not isinstance(raw_payload['transparent_background'],bool):
        raise c.ConfigError('图片需求类型不正确')
    for lookup_key in ('min_width','min_height'):
        if type(raw_payload[lookup_key]) is not int or not 1<=raw_payload[lookup_key]<=16384:raise c.ConfigError('尺寸须为1—16384的整数')
    if raw_payload['operation']=='edit' and not raw_payload['references']:raise c.ConfigError('改图需要明确输入图片')
    reference_list=[]
    for element_item in raw_payload['references']:
        if not isinstance(element_item,str):raise c.ConfigError('参考图须为本地文件路径')
        input_path=Path(element_item).expanduser()
        if not input_path.is_absolute():input_path=Path(path).resolve().parent/input_path
        metadata_map=perform_inspect_image(input_path)
        reference_list.append({'path':str(input_path.resolve()),'sha256':metadata_map['sha256']})
    raw_payload['references']=reference_list
    return raw_payload


def perform_choose(config, runtime_value=None, request=None, mode=None, provider=None, grants=()):
    pref_entries=config['preferences']['image']; chosen_option=mode or pref_entries['mode']
    outcome_payload={'capability':'image','mode':chosen_option,'status':'ready','reasons':[]}
    if config['policy']['image_generation']=='deny' and chosen_option=='generate':
        return dict(outcome_payload,status='blocked',reasons=['图片生成已被明确禁止'])
    if chosen_option=='off':return dict(outcome_payload,status='skipped',reasons=['不启用图片生成'])
    if chosen_option=='existing':return dict(outcome_payload,status='needs_input',reasons=['提供现有图片，通过use-image导入'])
    if chosen_option=='unconfigured':return dict(outcome_payload,status='needs_configuration',prompt=config['onboarding']['image']!='manual',reasons=['可选现有素材、当前宿主生图或跳过'])
    if chosen_option!='generate':raise c.ConfigError('图片方式不支持')
    if not runtime_value:return dict(outcome_payload,status='needs_runtime',reasons=['需当前会话实际暴露的工具快照；不能按Agent名称推断'])
    request=request or {'operation':'generate','references':[],'transparent_background':False}
    selected_value=provider or pref_entries['provider']
    candidates=[]
    for tool in runtime_value['tools']:
        if selected_value!='auto' and tool['id']!=selected_value:continue
        if request['operation'] not in tool['operations']:continue
        if request['references'] and not tool['reference_images']:continue
        if request['transparent_background'] and not tool['transparent_background']:continue
        candidates.append(tool)
    if not candidates:return dict(outcome_payload,status='unavailable',reasons=['当前无满足要求的工具；可导入现有素材，不自动接API'])
    ready=[];missing_value=[];blocked=[]
    for tool in candidates:
        needs=['image_generation']
        if tool['network']=='cloud':needs.append('cloud')
        if tool['cost']=='paid_api':needs.append('paid_api')
        if tool['cost']=='unknown':needs.append('unknown_image_cost')
        if request['references'] and tool['network']=='cloud':needs.append('reference_upload')
        deny=[sort_key for sort_key in needs if config['policy'][sort_key]=='deny']
        ask_value=[sort_key for sort_key in needs if config['policy'][sort_key]!='allow' and sort_key not in grants]
        if deny:blocked.append({'tool_id':tool['id'],'denied':deny})
        elif ask_value:missing_value.append({'tool_id':tool['id'],'needs':ask_value})
        else:ready.append(tool)
    if len(ready)>1:return dict(outcome_payload,status='needs_selection',candidates=[sample_value['id'] for sample_value in ready],reasons=['多个工具可用，请选择本次供应商或设置偏好'])
    if not ready:
        return dict(outcome_payload,status='needs_permission' if missing_value else 'blocked',candidates=missing_value or blocked,reasons=['探查不授予调用权；沿用用户已经明确的本次授权'])
    return dict(outcome_payload,status='host_action_required',host=runtime_value['host'],tool=ready[0],operation=request['operation'],
                reasons=['由当前Agent按真实工具schema执行；Python不会调用宿主工具'])


def perform_no_overwrite(path, payload_value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream_handle:stream_handle.write(payload_value)


def perform_config_fingerprint(config):
    selected_value={'preferences':config['preferences']['image'], 'policy':{sort_key:config['policy'][sort_key] for sort_key in ('image_generation','cloud','paid_api','reference_upload','unknown_image_cost')}}
    return hashlib.sha256(json.dumps(selected_value,sort_keys=True).encode()).hexdigest()


def compose_plan(config, request, runtime_value, session, out, mode=None, provider=None, grants=()):
    decision_value=perform_choose(config,runtime_value,request,mode,provider,grants)
    if decision_value['status']!='host_action_required':return decision_value
    plan={'schema_version':1,'plan_id':str(uuid.uuid4()),'session_id':session,'created_at':time.time(),
          'host':runtime_value['host'],'tool':decision_value['tool'],'request':request,'configuration_sha256':perform_config_fingerprint(config),
          'instruction':'Agent调用当前真实工具；成功后保存回执，accept-image重新核验授权与产物。'}
    perform_no_overwrite(out,(json.dumps(plan,ensure_ascii=False,indent=2)+'\n').encode())
    return {'status':'host_action_required','plan':str(out),'plan_id':plan['plan_id'],'tool_id':plan['tool']['id']}


def accept(config, active_plan_path, active_receipt_path, file, out, runtime_value, session, grants=()):
    plan=c.read_json(Path(active_plan_path));receipt=c.read_json(Path(active_receipt_path))
    if plan.get('schema_version')!=1 or plan.get('session_id')!=session or plan.get('host')!=runtime_value['host']:
        raise c.ConfigError('计划不属于当前宿主/会话')
    created_value=plan.get('created_at')
    if not isinstance(created_value,(int,float)) or not 0<=time.time()-created_value<=3600:
        raise c.ConfigError('图片计划超过1小时，重新解析当前授权与要求')
    if plan.get('configuration_sha256')!=perform_config_fingerprint(config):
        raise c.ConfigError('图片相关配置已改变，请重新生成计划')
    req_value=plan.get('request')
    if not isinstance(req_value,dict) or not isinstance(req_value.get('prompt'),str) or req_value.get('operation') not in ('generate','edit') or not isinstance(req_value.get('references'),list) or type(req_value.get('transparent_background')) is not bool:
        raise c.ConfigError('图片计划的需求结构无效')
    if any(type(req_value.get(sort_key)) is not int or not 1<=req_value[sort_key]<=16384 for sort_key in ('min_width','min_height')):
        raise c.ConfigError('图片计划尺寸无效')
    for reference_value in req_value['references']:
        if not isinstance(reference_value,dict) or not isinstance(reference_value.get('path'),str) or not isinstance(reference_value.get('sha256'),str):
            raise c.ConfigError('计划参考图结构无效')
    tool=plan.get('tool',{})
    if not isinstance(tool,dict):raise c.ConfigError('计划工具声明无效')
    current_value=next((elapsed_seconds for elapsed_seconds in runtime_value['tools'] if elapsed_seconds['id']==tool.get('id')),None)
    if current_value!=tool:raise c.ConfigError('工具能力发生变化或已不可用，不能复用旧计划')
    for reference_value in plan['request']['references']:
        if perform_sha(reference_value['path'])!=reference_value['sha256']:raise c.ConfigError('参考图已变化，重新生成计划')
    decision_value=perform_choose(config,runtime_value,plan['request'],mode='generate',provider=tool['id'],grants=grants)
    if decision_value['status']!='host_action_required':raise c.ConfigError('当前配置不再允许接收该生成任务：'+decision_value['status'])
    metadata_map=perform_inspect_image(file)
    expected_value={'status':'success','plan_id':plan['plan_id'],'session_id':session,'tool_id':tool['id'],'output_sha256':metadata_map['sha256']}
    if any(receipt.get(sort_key)!=current_value_x for sort_key,current_value_x in expected_value.items()):raise c.ConfigError('回执未成功或与计划/文件不一致')
    req_value=plan['request']
    if not metadata_map['has_visible_pixels']:raise c.ConfigError('生成图片全透明，缺少可见内容')
    if metadata_map['width']<req_value['min_width'] or metadata_map['height']<req_value['min_height']:
        raise c.ConfigError('图片尺寸小于任务要求')
    if req_value['transparent_background'] and not metadata_map['has_transparency']:
        raise c.ConfigError('要求透明背景，但产物没有实际透明像素')
    metadata_map.update(generated=True,tool_id=tool['id'],host=runtime_value['host'],plan_id=plan['plan_id'],
                prompt_sha256=hashlib.sha256(req_value['prompt'].encode()).hexdigest(),receipt_sha256=perform_sha(active_receipt_path),
                provenance='agent_reported_tool_call',source_proof='回执关联已检查，非平台签名来源认证')
    return perform_import_artifact(file,out,metadata_map)


def perform_import_artifact(file,out,metadata_map):
    out=Path(out);sidecar_value=out.with_name(out.name+'.json')
    suffix={'.png':'png','.jpg':'jpeg','.jpeg':'jpeg','.webp':'webp'}.get(out.suffix.lower())
    if suffix!=metadata_map['format']:raise c.ConfigError('目标扩展名须与真实图片格式一致；此入口不转码')
    if out.exists() or sidecar_value.exists():raise c.ConfigError('目标图片或元数据已存在，请使用新版本文件名')
    payload_value=Path(file).read_bytes()
    if hashlib.sha256(payload_value).hexdigest()!=metadata_map['sha256']:raise c.ConfigError('验收期间图片已改变')
    metadata_map=dict(metadata_map,path=out.name)
    # 配对写入由协作脚本锁串行；不覆盖用户现有版本。
    with c.locked(out):
        if out.exists() or sidecar_value.exists():raise c.ConfigError('目标已被其他进程创建')
        perform_no_overwrite(out,payload_value)
        perform_no_overwrite(sidecar_value,(json.dumps(metadata_map,ensure_ascii=False,indent=2)+'\n').encode())
    return {'status':'complete','output':str(out),'metadata':str(sidecar_value),'sha256':metadata_map['sha256']}


def run_cli():
    input_path=argparse.ArgumentParser(description=__doc__);segment_record=input_path.add_subparsers(dest='command',required=True)
    for name in ('image-status','image-plan','accept-image','use-image'):
        query_value=segment_record.add_parser(name);query_value.add_argument('--config');query_value.add_argument('--project')
        if name!='use-image':
            query_value.add_argument('--host-tools');query_value.add_argument('--session')
            for lookup_key in ('image-generation','cloud','paid-api','reference-upload','unknown-image-cost'):
                query_value.add_argument('--allow-'+lookup_key,action='store_true',help='仅表达已有的本次授权，不覆盖deny')
        if name in ('image-status','image-plan'):
            query_value.add_argument('--mode',choices=['off','existing','generate']);query_value.add_argument('--provider')
            query_value.add_argument('--request',required=name=='image-plan')
        if name in ('image-plan','accept-image','use-image'):query_value.add_argument('--out',required=True)
        if name in ('accept-image','use-image'):query_value.add_argument('--file',required=True)
        if name=='accept-image':query_value.add_argument('--plan',required=True);query_value.add_argument('--receipt',required=True)
    alpha_channel=input_path.parse_args();config,_ignored=c.effective(alpha_channel.config,alpha_channel.project)
    grants=[lookup_key for lookup_key in ('image_generation','cloud','paid_api','reference_upload','unknown_image_cost') if getattr(alpha_channel,'allow_'+lookup_key,False)]
    runtime_value=perform_runtime_tools(alpha_channel.host_tools,alpha_channel.session) if getattr(alpha_channel,'host_tools',None) else None
    if alpha_channel.command=='use-image':
        metadata_map=perform_inspect_image(alpha_channel.file);metadata_map.update(generated=False,mode='existing',provenance='provided_file')
        outcome_payload=perform_import_artifact(alpha_channel.file,alpha_channel.out,metadata_map)
    elif alpha_channel.command=='accept-image':
        if not runtime_value:raise c.ConfigError('需要本次最新宿主工具快照')
        outcome_payload=accept(config,alpha_channel.plan,alpha_channel.receipt,alpha_channel.file,alpha_channel.out,runtime_value,alpha_channel.session,grants)
    else:
        request=perform_request_data(alpha_channel.request) if alpha_channel.request else None
        if alpha_channel.command=='image-status':outcome_payload=perform_choose(config,runtime_value,request,alpha_channel.mode,alpha_channel.provider,grants)
        else:
            if not runtime_value:raise c.ConfigError('需要本次宿主工具快照，不能猜测工具')
            outcome_payload=compose_plan(config,request,runtime_value,alpha_channel.session,alpha_channel.out,alpha_channel.mode,alpha_channel.provider,grants)
    print(json.dumps(outcome_payload,ensure_ascii=False,indent=2))
    if alpha_channel.command=='image-plan' and outcome_payload['status']!='host_action_required':raise SystemExit(2)


if __name__=='__main__':
    try:run_cli()
    except (c.ConfigError,OSError,ValueError,KeyError,TypeError) as caught_error:
        print(json.dumps({'status':'error','message':str(caught_error) if isinstance(caught_error,c.ConfigError) else type(caught_error).__name__},ensure_ascii=False),file=sys.stderr)
        raise SystemExit(2)
