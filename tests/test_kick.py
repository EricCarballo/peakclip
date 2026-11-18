import tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from urllib.error import HTTPError
from peakclip.platforms import kick

SAMPLE_CHANNEL={
    'id':668,'slug':'xqc','followers_count':10,
    'user':{'username':'xQc','bio':'bio','profilepic':''},
    'livestream':None,'chatroom':{'id':668},
}
SAMPLE_VIDEO_LIST=[{
    'id':1,'channel_id':668,'session_title':'Live now','duration':0,'is_live':True,
    'start_time':'2026-11-14 22:41:47','source':'https://example.com/live.m3u8',
    'views':9,'slug':'live-slug',
    'thumbnail':{'src':'https://example.com/t.webp'},
    'video':{'uuid':'aaaaaaaa-9aaa-4e7a-b88e-22b50c6194b0','views':9},
},{
    'id':2,'channel_id':668,'session_title':'Test stream','duration':120000,'is_live':False,
    'start_time':'2026-11-14 22:41:47','source':'https://example.com/master.m3u8',
    'views':9,'slug':'test-slug',
    'thumbnail':{'src':'https://example.com/t.webp'},
    'video':{'uuid':'371f0495-9aaa-4e7a-b88e-22b50c6194b0','views':9},
}]

class KickLinks(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(kick.parse_link('kick.com/Xqc'),('channel','xqc'))
        self.assertEqual(kick.parse_link('https://kick.com/xqc/videos/371f0495-9aaa-4e7a-b88e-22b50c6194b0'),('video','371f0495-9aaa-4e7a-b88e-22b50c6194b0'))
    @patch('peakclip.platforms.kick.get_json')
    def test_inspect_channel(self,get_json):
        get_json.side_effect=[SAMPLE_CHANNEL,SAMPLE_VIDEO_LIST]
        data=kick.inspect('https://kick.com/xqc')
        self.assertEqual(data['platform'],'kick')
        self.assertEqual(data['channel']['login'],'xqc')
        # Live entries are skipped so clipping always gets finished VODs.
        self.assertEqual(len(data['videos']),1)
        self.assertEqual(data['videos'][0]['id'],'371f0495-9aaa-4e7a-b88e-22b50c6194b0')
        self.assertEqual(data['videos'][0]['lengthSeconds'],120)
        self.assertTrue(data['videos'][0]['source'])
        self.assertFalse(data['videos'][0].get('is_live'))
    def test_estimate_duration_for_live_window(self):
        start='2026-11-14T22:41:47+00:00'
        item={'duration':0,'is_live':True,'start_time':start,'video':{'uuid':'bbbbbbbb-9aaa-4e7a-b88e-22b50c6194b0'}}
        video=kick.normalize_video(item,'xqc')
        self.assertTrue(video['is_live'])
        self.assertGreater(video['lengthSeconds'],0)
    @patch('peakclip.platforms.kick.get_json')
    def test_inspect_rejects_live_video_link(self,get_json):
        get_json.return_value={
            'source':'https://example.com/master.m3u8','views':1,'uuid':'cccccccc-9aaa-4e7a-b88e-22b50c6194b0',
            'livestream':{
                'is_live':True,'duration':0,'session_title':'Live','channel_id':668,
                'start_time':'2026-11-14 22:41:47','source':'https://example.com/master.m3u8',
                'channel':{'id':668,'slug':'xqc','user':{'username':'xQc','bio':'','profilepic':''},'followers_count':1},
            },
        }
        with self.assertRaisesRegex(ValueError,'sigue en vivo'):
            kick.inspect('https://kick.com/xqc/videos/cccccccc-9aaa-4e7a-b88e-22b50c6194b0')
    @patch('peakclip.platforms.kick.time.sleep',return_value=None)
    @patch('peakclip.platforms.kick.get_json')
    def test_download_chat_window(self,get_json,sleep):
        get_json.side_effect=[
            {'data':{'messages':[
                {'id':'1','content':'hola','created_at':'2026-11-14T22:42:10Z'},
                {'id':'2','content':'antes','created_at':'2026-11-14T22:40:00Z'},
            ],'cursor':None}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'chat.json'
            count=kick.download_chat(668,'2026-11-14T22:41:47+00:00',120,dest)
            self.assertEqual(count,1)
            text=dest.read_text(encoding='utf-8')
            self.assertIn('hola',text)
            self.assertNotIn('antes',text)
            cursor=get_json.call_args.args[0]
            self.assertIn('cursor=',cursor)
            # Cursor seeding uses epoch microseconds for Kick replay.
            self.assertGreater(len(cursor.split('cursor=')[1]),12)
    @patch('peakclip.platforms.kick.time.sleep',return_value=None)
    @patch('peakclip.platforms.kick.get_json')
    def test_download_chat_resumes_from_checkpoint(self,get_json,sleep):
        get_json.side_effect=[
            {'data':{'messages':[
                {'id':'3','content':'despues','created_at':'2026-11-14T22:42:20Z'},
                {'id':'2','content':'antes','created_at':'2026-11-14T22:40:00Z'},
            ],'cursor':None}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'chat.json'
            checkpoint=Path(tmp)/'progress.json'
            kick.save_chat_progress(checkpoint,{
                'channel_id':'668',
                'start_iso':'2026-11-14T22:41:47+00:00',
                'duration':120,
                'cursor':'999',
                'pages':2,
                'complete':False,
                'comments':[{'id':'1','content_offset_seconds':5,'message':{'body':'hola'}}],
            })
            count=kick.download_chat(668,'2026-11-14T22:41:47+00:00',120,dest,checkpoint=checkpoint)
            self.assertEqual(count,2)
            text=dest.read_text(encoding='utf-8')
            self.assertIn('hola',text)
            self.assertIn('despues',text)
            saved=kick.load_chat_progress(checkpoint)
            self.assertTrue(saved['complete'])
    @patch('peakclip.platforms.kick.time.sleep',return_value=None)
    @patch('peakclip.platforms.kick.urlopen')
    def test_get_json_retries_429_then_succeeds(self,urlopen,sleep):
        ok=Mock(); ok.read.return_value=b'{"ok":true}'; ok.__enter__=Mock(return_value=ok); ok.__exit__=Mock(return_value=False)
        err=HTTPError('https://kick.com/x',429,'Too Many Requests',hdrs=None,fp=None)
        urlopen.side_effect=[err,ok]
        notes=[]
        data=kick.get_json('https://kick.com/api/v2/channels/1/messages',on_retry=lambda *a:notes.append(a))
        self.assertEqual(data,{'ok':True})
        self.assertTrue(notes)
        self.assertEqual(notes[0][0],429)
    @patch('peakclip.platforms.kick.time.sleep',return_value=None)
    @patch('peakclip.platforms.kick.urlopen')
    def test_get_json_429_friendly_message(self,urlopen,sleep):
        err=HTTPError('https://kick.com/x',429,'Too Many Requests',hdrs=None,fp=None)
        urlopen.side_effect=[err]*8
        with self.assertRaises(kick.KickError) as ctx:
            kick.get_json('https://kick.com/api/v2/channels/1/messages',retries=3)
        self.assertNotIn('429',str(ctx.exception))
        self.assertIn('limitando',str(ctx.exception).lower())

if __name__=='__main__':unittest.main()
