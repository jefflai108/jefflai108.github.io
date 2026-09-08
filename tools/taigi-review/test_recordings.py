"""Real audio conversion and shared recording API, using only synthetic test audio."""
import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import unittest
import uuid
import wave
import test_server
import recordings

class RecordingTests(unittest.TestCase):
    setUp=test_server.ReviewTests.setUp
    tearDown=test_server.ReviewTests.tearDown
    call=test_server.ReviewTests.call
    def make_payload(self, data=None, mime='audio/wav'):
        if data is None: data=(self.root/'audio/taigi-00000000.wav').read_bytes()
        return {'id':'rec-'+str(uuid.uuid4()),'title':'我的台語','annotation':'逐家好','status':'unreviewed','editor':'Alice','mime':mime,'audio_base64':base64.b64encode(data).decode()}
    def test_audio_upload_persistence_and_separate_dev_dataset(self):
        before=self.call('/api/export')[2]
        p=self.make_payload();code,_,data=self.call('/api/recordings',p,method='POST')
        self.assertEqual(code,201);record=data['recording'];self.assertEqual(record['annotation'],'逐家好')
        self.assertNotIn('audio_wav',record);self.assertNotIn('upload_sha256',record)
        status,h,audio=self.call('/api/recordings/'+p['id']+'/audio')
        self.assertEqual(status,200);self.assertEqual(h['Content-Type'],'audio/wav')
        with wave.open(io.BytesIO(audio)) as wav:self.assertEqual(wav.getframerate(),16000);self.assertEqual(wav.getnchannels(),1)
        self.assertEqual(self.call('/api/recordings?'+ 'q=逐家')[2]['total'],1)
        self.assertEqual(self.call('/api/export')[2]['clips'],before['clips'])
        self.assertEqual(self.call('/api/meta')[2]['stats']['total'],2)
        recordings.initialize(self.db)
        self.assertEqual(self.call('/api/recordings/'+p['id'])[2]['recording']['annotation'],'逐家好')
        with closing(sqlite3.connect(self.db)) as source,closing(sqlite3.connect(self.root/'backup.sqlite3')) as backup:
            source.backup(backup)
            self.assertGreater(backup.execute('SELECT length(audio_wav) FROM recordings').fetchone()[0],100)
    def test_idempotent_upload_retry_never_overwrites_shared_annotation(self):
        p=self.make_payload();self.assertEqual(self.call('/api/recordings',p,method='POST')[0],201)
        path='/api/recordings/'+p['id']
        edit={'annotation':'咱做伙講台語','status':'reviewed','revision':0,'editor':'Bob'}
        self.assertEqual(self.call(path,edit)[0],200)
        self.assertEqual(self.call('/api/recordings',p,method='POST')[2]['recording']['annotation'],edit['annotation'])
        self.assertEqual(self.call('/api/recordings')[2]['total'],1)
        self.assertEqual(len(self.call(path+'/history')[2]['history']),2)
        altered=p|{'audio_base64':base64.b64encode(b'X'*100).decode()}
        self.assertEqual(self.call('/api/recordings',altered,method='POST')[0],409)
        self.assertEqual(self.call(path,edit|{'annotation':'stale','revision':0})[0],409)
    def test_simultaneous_upload_is_deduplicated(self):
        p=self.make_payload()
        with ThreadPoolExecutor(max_workers=2) as pool:
            codes=list(pool.map(lambda _:self.call('/api/recordings',p,method='POST')[0],range(2)))
        self.assertEqual(sorted(codes),[200,201]);self.assertEqual(self.call('/api/recordings')[2]['total'],1)
    def test_real_webm_and_mp4_capture_formats(self):
        for ext,mime,codec in [('webm','audio/webm;codecs=opus','libopus'),('m4a','audio/mp4','aac')]:
            path=self.root/('test.'+ext)
            subprocess.run(['/opt/homebrew/bin/ffmpeg','-nostdin','-v','error','-i',str(self.root/'audio/taigi-00000000.wav'),'-c:a',codec,str(path)],check=True)
            code,_,data=self.call('/api/recordings',self.make_payload(path.read_bytes(),mime),method='POST')
            self.assertEqual(code,201,data)
    def test_unauthorized_invalid_and_range_requests(self):
        p=self.make_payload()
        self.assertEqual(self.call('/api/recordings',p,method='POST',auth=False)[0],401)
        self.assertEqual(self.call('/api/recordings',p|{'id':'../../secret'},method='POST')[0],400)
        self.assertEqual(self.call('/api/recordings',p|{'audio_base64':'not-audio'},method='POST')[0],400)
        self.assertEqual(self.call('/api/recordings',p|{'audio_base64':base64.b64encode(b'X'*100).decode()},method='POST')[0],400)
        self.assertEqual(self.call('/api/recordings',p,method='POST')[0],201)
        path='/api/recordings/'+p['id']
        self.assertEqual(self.call(path+'/audio',auth=False)[0],401)
        self.assertEqual(self.call(path+'/audio',headers={'Range':'bytes=0-43'})[0],206)
        self.assertEqual(self.call(path+'/audio',headers={'Range':'bytes=999999-'})[0],416)
        self.assertEqual(self.call(path,{'annotation':'','status':'reviewed','revision':0,'editor':'Bob'})[0],200)
        self.assertEqual(self.call('/api/recordings',p,method='POST',headers={'Origin':'https://evil.example'})[0],403)

if __name__=='__main__':unittest.main()
