#!/usr/bin/env python3
import json, hashlib, re, time
from datetime import datetime, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
PROGRAMS_PATH=ROOT/'data'/'programs.json'
HISTORY_PATH=ROOT/'data'/'status-history.json'
HEADERS={'User-Agent':'Mozilla/5.0 program-tracker-bot/1.0; educational personal tracker'}
SIGNAL_PATTERNS=[r'application deadline[:\s]+[^.\n]{0,120}',r'applications? (are )?(now )?(open|closed)',r'apply (now|by)[^.\n]{0,120}',r'deadline[:\s]+[^.\n]{0,120}',r'competition[:\s]+[^.\n]{0,120}',r'selected applicants?[^.\n]{0,120}',r'first[- ]year[^.\n]{0,120}',r'sophomore[^.\n]{0,120}']
def clean_text(html):
    soup=BeautifulSoup(html,'html.parser')
    for tag in soup(['script','style','noscript','svg']): tag.decompose()
    return re.sub(r'\s+',' ',soup.get_text(' ',strip=True))
def extract_signals(text,keywords):
    matches=[]; lower=text.lower()
    for pattern in SIGNAL_PATTERNS:
        for m in re.finditer(pattern,text,flags=re.I): matches.append(m.group(0)[:180])
    for kw in keywords or []:
        kl=kw.lower()
        if kl and kl in lower:
            idx=lower.find(kl); matches.append(text[max(0,idx-60):idx+140])
    seen=set(); out=[]
    for m in matches:
        norm=m.lower()
        if norm not in seen:
            seen.add(norm); out.append(m)
    return out[:8]
def fetch_one(program,previous):
    url=program.get('official_url','').strip()
    if not url: return None
    rec={'company':program.get('company'),'program':program.get('program'),'url':url,'checked_at':datetime.now(timezone.utc).isoformat(),'ok':False,'http_status':None,'changed':False,'status_text':'','latest_match':'','signals':[],'error':''}
    try:
        resp=requests.get(url,headers=HEADERS,timeout=25); rec['http_status']=resp.status_code; resp.raise_for_status()
        text=clean_text(resp.text); digest=hashlib.sha256(text.encode()).hexdigest(); old=previous.get(url,{}).get('content_hash')
        rec['content_hash']=digest; rec['changed']=bool(old and old!=digest); rec['ok']=True
        signals=extract_signals(text,program.get('keywords',[])); rec['signals']=signals; rec['latest_match']=signals[0] if signals else ''
        low=text.lower()
        if 'applications are now closed' in low or 'applications closed' in low: rec['status_text']='Applications may be closed'
        elif 'application deadline' in low or 'apply now' in low or 'apply by' in low: rec['status_text']='Application/deadline signal found'
        elif rec['changed']: rec['status_text']='Page changed since last check'
        else: rec['status_text']='No clear application signal'
    except Exception as e:
        rec['error']=str(e)[:300]
        old=previous.get(url)
        if old: rec['content_hash']=old.get('content_hash')
    return rec
def main():
    data=json.loads(PROGRAMS_PATH.read_text(encoding='utf-8'))
    try: previous=json.loads(HISTORY_PATH.read_text(encoding='utf-8'))
    except Exception: previous={}
    new={}
    for program in data.get('programs',[]):
        rec=fetch_one(program,previous)
        if rec:
            new[program['official_url']]=rec
            print(f"{rec['company']} - {rec['program']}: {rec['status_text']}")
            time.sleep(1.2)
    HISTORY_PATH.write_text(json.dumps(new,indent=2,ensure_ascii=False),encoding='utf-8')
    data['generated_at']=datetime.now(timezone.utc).isoformat()
    PROGRAMS_PATH.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
if __name__=='__main__': main()
