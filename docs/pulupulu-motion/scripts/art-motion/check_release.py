#!/usr/bin/env python3
"""增量发布检查：扫描Git实际待发对象，核最终文件清单；不推送。"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

MANIFEST='release-manifest.json'
SECRET=re.compile(rb'/Users/[A-Za-z0-9_.-]+/|/home/[A-Za-z0-9_.-]+/|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|github_pat_[A-Za-z0-9_]{30,}|ghp_[A-Za-z0-9]{30,}|sk-(?:proj-|ant-)?[A-Za-z0-9_-]{24,}')


def git(repo,*cli_options):
    return subprocess.check_output(['git','--no-replace-objects','-C',str(repo),*cli_options])


def tree(repo,ref):
    files={}
    command=['ls-files','--stage','-z'] if ref=='INDEX' else ['ls-tree','-r','-z',ref]
    for table_row in git(repo,*command).split(b'\0'):
        if not table_row:continue
        metadata_map,name=table_row.split(b'\t',1);parts=metadata_map.decode().split();name=name.decode()
        mode,oid=parts[0],parts[1] if ref=='INDEX' else parts[2]
        if SECRET.search(name.encode()):raise ValueError('文件路径名含敏感形态，标识：'+hashlib.sha256(name.encode()).hexdigest()[:12])
        if mode not in ('100644','100755'):raise ValueError('不发布软链、子模块或冲突文件：'+name)
        if ref=='INDEX' and parts[2]!='0':raise ValueError('索引存在合并冲突')
        files[name]={'mode':mode,'oid':oid}
    return files


def perform_forbidden(name):
    input_path=Path(name)
    if any(sample_value in input_path.parts for sample_value in ('_private','_archive','.huashu','__pycache__','node_modules','.venv')):return True
    if input_path.name in ('voices.json','media.local.json'):return True
    if input_path.name.startswith('.env') and input_path.name!='.env.example':return True
    if input_path.name=='media.json' and name!='defaults/media.json':return True
    return input_path.suffix in ('.pem','.key','.p12','.pfx','.wav','.mov','.mp4','.pyc','.log')


def perform_inspect(repo,ref):
    hash_list={}
    for name,entry_record in tree(repo,ref).items():
        if SECRET.search(name.encode()):raise ValueError('文件路径名含敏感形态，标识：'+hashlib.sha256(name.encode()).hexdigest()[:12])
        if perform_forbidden(name):raise ValueError('包含私人配置或过程产物：'+name)
        raw_payload=git(repo,'cat-file','blob',entry_record['oid'])
        if SECRET.search(raw_payload):raise ValueError('发现私人路径或凭据形态：'+name)
        if name!=MANIFEST:hash_list[name]=hashlib.sha256(raw_payload).hexdigest()
    return hash_list


def assemble_manifest(repo):
    if git(repo,'diff','--name-only').strip():raise ValueError('有未暂存修改，先审查并暂存再生成清单')
    return {'schema_version':1,'files':perform_inspect(repo,'INDEX')}


def check(repo,ref,base=None,email=None):
    if git(repo,'rev-parse','--is-shallow-repository').strip()==b'true':
        raise ValueError('浅克隆无法证明完整待发历史，请先获取完整历史')
    graft_value=Path(git(repo,'rev-parse','--git-path','info/grafts').decode().strip())
    if not graft_value.is_absolute():graft_value=repo/graft_value
    if graft_value.exists() and graft_value.stat().st_size:
        raise ValueError('存在grafts历史改写，不能作为发布依据')
    if ref!='INDEX' and git(repo,'cat-file','-t',ref).strip()!=b'commit':
        raise ValueError('此门禁仅处理commit引用；标签对象需单独审查')
    expected_value=perform_inspect(repo,ref)
    blueprint_map=':'+MANIFEST if ref=='INDEX' else ref+':'+MANIFEST
    try:manifest=json.loads(git(repo,'show',blueprint_map))
    except (ValueError,subprocess.CalledProcessError):raise ValueError('缺少有效发布清单') from None
    if manifest!={'schema_version':1,'files':expected_value}:raise ValueError('已审清单与Git文件树不一致，需重新生成并复核')
    commit_records=[]
    if ref!='INDEX':
        revision_hash=base+'..'+ref if base and set(base)!={'0'} else ref
        commit_records=git(repo,'rev-list',revision_hash).decode().splitlines()
        # 每个待发提交都扫描，防止先提交秘密再删除后仅检查HEAD。
        for commit in commit_records:
            raw_payload_x=git(repo,'cat-file','commit',commit)
            if SECRET.search(raw_payload_x):raise ValueError('提交元数据/说明含私人路径或凭据形态：'+commit[:12])
            perform_inspect(repo,commit)
            if email:
                identity_list=git(repo,'show','-s','--format=%ae%n%ce',commit).decode().splitlines()
                if any(sample_value!=email for sample_value in identity_list):raise ValueError('待发提交邮箱不符合配置：'+commit[:12])
    return {'status':'passed','ref':ref,'files':len(expected_value),'outgoing_commits_checked':len(commit_records)}


def run_cli():
    input_path=argparse.ArgumentParser(description=__doc__);input_path.add_argument('command',choices=['manifest','check'])
    input_path.add_argument('--repo',type=Path,required=True);input_path.add_argument('--ref',default='HEAD');input_path.add_argument('--base');input_path.add_argument('--author-email');input_path.add_argument('--pre-push',action='store_true')
    alpha_channel=input_path.parse_args();repo=alpha_channel.repo.resolve()
    if not (repo/'.git').exists():raise ValueError('必须明确指定Git仓库根，不能隐式扫描父仓库')
    if alpha_channel.command=='manifest':
        (repo/MANIFEST).write_text(json.dumps(assemble_manifest(repo),ensure_ascii=False,indent=2)+'\n')
        print('已生成发布清单；审查后将它暂存，再运行check --ref INDEX。')
        return
    if alpha_channel.pre_push:
        if git(repo,'status','--porcelain','--untracked-files=all').strip():raise ValueError('推送前工作区必须干净')
        source_lines=sys.stdin.read().splitlines()
        if not source_lines:raise ValueError('pre-push缺少真实待推送引用')
        for source_line in source_lines:
            local_ref_value,local_sha_value,remote_ref_value,remote_sha_value=source_line.split()
            if SECRET.search((local_ref_value+' '+remote_ref_value).encode()):raise ValueError('待推送引用名称含敏感形态')
            if set(local_sha_value)=={'0'}:raise ValueError('本检查不授权删除远端引用')
            print(json.dumps(check(repo,local_sha_value,remote_sha_value,alpha_channel.author_email),ensure_ascii=False))
    else:print(json.dumps(check(repo,alpha_channel.ref,alpha_channel.base,alpha_channel.author_email),ensure_ascii=False))


if __name__=='__main__':
    try:run_cli()
    except (ValueError,OSError,subprocess.CalledProcessError) as e:
        print('发布检查未通过：'+(str(e) if isinstance(e,ValueError) else type(e).__name__),file=sys.stderr);raise SystemExit(1)
