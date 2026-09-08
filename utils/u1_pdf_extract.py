"""Bounded text-only PDF extraction worker. No OCR, scripts or network fetches."""
import io
import json
import sys


def extract(raw):
    if len(raw)>5*1024*1024 or not raw.startswith(b'%PDF-'):
        return {'success':False,'notice':'Expected a PDF no larger than 5 MB.'}
    from pypdf import PdfReader
    reader=PdfReader(io.BytesIO(raw),strict=False)
    if reader.is_encrypted:
        return {'success':False,'notice':'Encrypted PDF; automatic extraction was skipped.'}
    parts=[]
    for page in reader.pages[:10]:
        parts.append((page.extract_text() or '')[:8000])
        if sum(map(len,parts))>=12000:break
    value='\n'.join(parts)[:12000]
    return {'success':True,'text':value,'pages':len(reader.pages),'limited':len(reader.pages)>10 or len(value)>=12000,
            'notice':'Text-only extraction; confirm dates and amounts against the original. Scanned documents require OCR.'}


if __name__=='__main__':
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU,(8,8))
        raw=sys.stdin.buffer.read(5*1024*1024+1)
        result=extract(raw)
    except Exception:
        result={'success':False,'notice':'PDF text extraction unavailable. Review the original document.'}
    print(json.dumps(result))
