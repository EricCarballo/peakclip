import unittest, tempfile, io
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from peakclip.infrastructure.storage import prepare_output,OutputError,session_directory,safe_name,cleanup_workspace,temps_present,save_session,list_history,load_history
from peakclip.platforms.channel import avatar_color
from peakclip.social import drafts as social

class Regression(unittest.TestCase):
    def test_output_created_and_unique(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)/'nested'/'clips'
            a=prepare_output(str(base),'123','elded','ya falta poco gta6'); b=prepare_output(str(base),'123','elded','ya falta poco gta6')
            self.assertTrue(a.is_dir()); self.assertEqual(a,b)
            self.assertEqual(a,base/'elded'/'ya falta poco gta6')
            self.assertNotEqual(session_directory(a),session_directory(b))
            different=prepare_output(str(base),'456','elded','ya falta poco gta6')
            self.assertNotEqual(a,different)
    def test_custom_folder_label(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)/'clips'
            custom=prepare_output(str(base),'789','ribius','gta 6 ya ya ya',folder_label='highlights abril')
            self.assertEqual(custom,base/'ribius'/'highlights abril')
            same_stream=prepare_output(str(base),'789','ribius','gta 6 ya ya ya',folder_label='highlights abril')
            self.assertEqual(custom,same_stream)
            default_title=prepare_output(str(base),'790','ribius','gta 6 ya ya ya')
            self.assertEqual(default_title,base/'ribius'/'gta 6 ya ya ya')
    def test_cleanup_removes_scratch_keeps_clips(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)/'clips'
            out=prepare_output(str(base),'100','canal','directo')
            clip=out/'clip1_demo.mp4';clip.write_bytes(b'video')
            social=out/'clip1_demo.social.json';social.write_text('{}',encoding='utf-8')
            session=session_directory(out)
            (session/'chat.json').write_text('{"comments":[]}',encoding='utf-8')
            (session/'preview_1.jpg').write_bytes(b'jpg')
            self.assertTrue(temps_present(out))
            result=cleanup_workspace(out)
            self.assertTrue(result['ok'])
            self.assertGreaterEqual(result['removed'],2)
            self.assertFalse(temps_present(out))
            self.assertTrue(clip.is_file())
            self.assertTrue(social.is_file())
            self.assertTrue((out/'.peakclip-video.json').is_file())
            again=cleanup_workspace(out)
            self.assertTrue(again['already_clean'])
    def test_windows_safe_names(self):
        for value in ['../CON','CON','NUL.txt','a:b/c\\d?*','..','a'*200]:
            name=safe_name(value,'directo')
            self.assertLessEqual(len(name),81)
            self.assertFalse(any(c in name for c in '<>:"/\\|?*'))
            self.assertNotIn(name,['CON','NUL.txt','..'])
    def test_windows_block_is_actionable(self):
        with patch('peakclip.infrastructure.storage.Path.mkdir',side_effect=FileNotFoundError(2,'blocked')):
            with self.assertRaisesRegex(OutputError,'Usar carpeta local'): prepare_output('C:/blocked','123')
    def test_dominant_color_and_neutral(self):
        for rgb,expected in [((20,60,220),2),((220,40,20),0),((100,100,100),None)]:
            buffer=io.BytesIO();Image.new('RGB',(50,50),rgb).save(buffer,format='PNG')
            color=avatar_color(buffer.getvalue())
            if expected is None: self.assertIsNone(color)
            else:
                parts=list(map(int,color.split(',')));self.assertEqual(parts.index(max(parts)),expected)
    def test_session_history_reopens_social(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)/'clips'
            out=prepare_output(str(base),'9001','lonche','noche de clips',platform='kick')
            clip=out/'clip3_demo.mp4';clip.write_bytes(b'video')
            thumb=out/'clip3_demo.jpg';thumb.write_bytes(b'jpgdata')
            draft=social.suggest('noche de clips','lonche',[],0,40,platform_source='kick')
            social.save(clip,draft)
            save_session(out,[{
                'number':3,'ready':True,'path':str(clip),'filename':clip.name,
                'time':'0:00','end':'0:40','duration':40,'strength':4.2,
                'url':'https://kick.com/lonche/videos/9001','channel':'lonche',
                'video_title':'noche de clips','platform':'kick','thumbnail_file':str(thumb),
            }],{'channel':'lonche','title':'noche de clips','platform':'kick','vod':'9001'})
            rows=list_history([base])
            self.assertTrue(any(r['path']==str(out) for r in rows))
            loaded=load_history(out)
            self.assertEqual(loaded['channel'],'lonche')
            self.assertEqual(loaded['platform'],'kick')
            self.assertEqual(len(loaded['clips']),1)
            self.assertIn('platforms',loaded['clips'][0]['social'])
            self.assertTrue(loaded['clips'][0]['thumbnail'].startswith('data:image/jpeg;base64,'))

if __name__=='__main__': unittest.main()
