"""Deterministic heatmap ranking, chapter cues, optional LLM title/rerank."""
from dataclasses import dataclass, asdict
import json
import math
import re
import requests


@dataclass
class Candidate:
    start: float
    end: float
    score: float
    title: str
    reason: str
    source: str

    def data(self):
        return asdict(self)


def heatmap_score(points, start, end):
    total = 0.0
    weight = 0.0
    for p in points or []:
        try:
            a = float(p['start_time'])
            b = float(p['end_time'])
            value = float(p['value'])
        except (KeyError, TypeError, ValueError):
            continue
        overlap = max(0, min(end, b) - max(start, a))
        total += overlap * max(0.0, min(1.0, value))
        weight += overlap
    return round(total / weight, 4) if weight else 0.0


def clip_text(segments, start, end, limit=650):
    return ' '.join(s['text'] for s in segments
                    if s['end'] > start and s['start'] < end)[:limit]


def _importance(text):
    text = text.lower()
    points = 0.05
    if '?' in text: points += .08
    if any(v in text for v in ('ternyata', 'kenapa', 'rahasia', 'masalah', 'penting', 'bagaimana',
                               'why', 'how', 'secret', 'mistake', 'sebenarnya', 'jangan')):
        points += .1
    if re.search(r'\b\d+[%kmb]?\b', text):
        points += .06
    points += min(.12, len(text)/1300)
    return points


def candidates_from_signals(duration, heatmap, segments, chapters=None, count=6, length=48):
    if duration <= 0:
        raise ValueError('Durasi video tidak valid')
    length = min(float(length), float(duration))
    pool = []
    heatmap = heatmap or []
    # Every heatmap cell can nominate a window; score overlapping intervals.
    if heatmap:
        for p in heatmap:
            try:
                center = (float(p['start_time']) + float(p['end_time'])) / 2
                start = max(0., min(duration-length, center-length/2))
                pool.append((start, 'heatmap'))
            except (TypeError, ValueError, KeyError):
                pass
    # Candidate windows also come from transcript/question cues and chapter openings.
    for s in segments or []:
        if '?' in s['text'] or any(x in s['text'].lower() for x in ('ternyata', 'kenapa', 'how', 'why')):
            pool.append((max(0, min(duration-length, float(s['start'])-5)), 'transcript'))
    for chapter in chapters or []:
        try:
            pool.append((max(0, min(duration-length, float(chapter['start_time']))), 'chapter'))
        except (KeyError, TypeError, ValueError):
            pass
    # Even coverage ensures there is always a meaningful offline fallback.
    stride = max(18, length*.85)
    for i in range(min(240, math.ceil(max(0, duration-length)/stride)+1)):
        pool.append((min(duration-length, i*stride), 'timeline'))
    proposals = []
    seen = set()
    for start, source in pool:
        # Round to 2s to deduplicate dense heatmap samples.
        key = round(start/2)
        if key in seen:
            continue
        seen.add(key)
        end = min(duration, start+length)
        heat = heatmap_score(heatmap, start, end)
        text = clip_text(segments, start, end)
        lexical = _importance(text) if text else 0
        score = (0.82*heat + 0.18*lexical) if heatmap else (0.6*lexical + .04)
        if source == 'chapter':
            score += .03
        title = (text[:60].strip(' ,.;') + ('…' if len(text)>60 else '')) if text else f'Momen {format_time(start)}'
        proposals.append(Candidate(round(start,2), round(end,2), round(score*100,1),
                                   title or 'Momen menarik',
                                   'Sinyal replay + konteks' if heatmap else 'Transkrip / timeline',
                                   source))
    proposals.sort(key=lambda x: x.score, reverse=True)
    results = []
    for c in proposals:
        if all(max(0, min(c.end, other.end)-max(c.start, other.start)) < length*.42
               for other in results):
            results.append(c)
        if len(results) >= count:
            break
    return sorted(results, key=lambda c: c.start)


def format_time(sec):
    sec = max(0, int(float(sec)))
    return f'{sec//3600:02d}:{(sec//60)%60:02d}:{sec%60:02d}'


def parse_time(text):
    parts = text.strip().split(':')
    if not 1 <= len(parts) <= 3:
        raise ValueError('Waktu harus HH:MM:SS atau MM:SS')
    vals = [float(p) for p in parts]
    if any(v<0 for v in vals):
        raise ValueError('Waktu tidak boleh negatif')
    sec = 0.0
    for value in vals:
        sec = sec*60 + value
    return sec


def _read_json(text):
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.I)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find('{'), text.rfind('}')
        if start >= 0 and end > start:
            return json.loads(text[start:end+1])
        raise


def rerank_with_llm(candidates, segments, settings, api_key, log=lambda x: None):
    provider = settings.ai_provider
    if provider == 'off' or not segments:
        return candidates
    if provider != 'ollama' and not api_key:
        log('API key AI tidak tersedia; menggunakan ranking offline.')
        return candidates
    payload_candidates = []
    for i, c in enumerate(candidates):
        payload_candidates.append({'id': i, 'start': c.start, 'end': c.end,
                                   'heatmap_score': c.score,
                                   'transcript': clip_text(segments, c.start, c.end, 950)})
    sys_prompt = ('Anda adalah editor video podcast Indonesia. Nilai cuplikan yang sudah tersedia, '
                  'pertahankan rentang waktu masing-masing. Balas JSON saja, format '
                  '{"clips":[{"id":0,"title":"judul singkat",'
                  '"score":75,"reason":"alasan singkat"}]}. '
                  'Nilai 0..100 berdasarkan hook, konteks lengkap, kejelasan, dan replay. '
                  'Jangan menciptakan id lain atau klaim tentang video di luar teks.')
    messages = [{'role':'system','content':sys_prompt},
                {'role':'user','content':json.dumps(payload_candidates,ensure_ascii=False)}]
    if provider == 'ollama':
        endpoint = settings.ollama_url.rstrip('/') + '/api/chat'
        body = {'model':settings.ollama_model,'messages':messages,'stream':False,
                'format':'json','options':{'temperature':0.2}}
        response = requests.post(endpoint,json=body,timeout=240)
        response.raise_for_status()
        content = response.json().get('message',{}).get('content','')
    else:
        endpoint = ('https://openrouter.ai/api/v1/chat/completions' if provider=='openrouter'
                    else settings.kie_endpoint)
        if not endpoint.startswith('https://'):
            raise ValueError('Endpoint AI cloud harus menggunakan HTTPS.')
        body = {'messages':messages,'temperature':0.2,'max_tokens':1400,'stream':False}
        if provider == 'openrouter':
            body['model'] = settings.ai_model
        # Kie endpoint selects model by URL; check its documentation for the selected model.
        response = requests.post(endpoint,json=body,
                                 headers={'Authorization':f'Bearer {api_key}',
                                          'Content-Type':'application/json'},timeout=150)
        response.raise_for_status()
        data = response.json()
        if data.get('code') not in (None,200):
            raise RuntimeError(f"AI provider: {data.get('msg', 'Error')}")
        content = data['choices'][0]['message']['content']
        if isinstance(content, list):
            content = ''.join(v.get('text','') for v in content if isinstance(v,dict))
    data = _read_json(content)
    proposed = data.get('clips',[]) if isinstance(data,dict) else []
    for result in proposed:
        try:
            idx = int(result['id'])
            if idx < 0 or idx >= len(candidates): continue
            c = candidates[idx]
            c.score = max(0., min(100., float(result.get('score',c.score))))
            c.title = str(result.get('title') or c.title)[:100]
            c.reason = str(result.get('reason') or c.reason)[:200]
            c.source += '+ai'
        except (ValueError, TypeError, KeyError):
            continue
    return sorted(candidates,key=lambda c: c.score,reverse=True)
