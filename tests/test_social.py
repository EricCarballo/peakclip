import tempfile,unittest,json
from pathlib import Path
from peakclip.social import drafts as social

class Drafts(unittest.TestCase):
    def test_local_context_and_platforms(self):
        data=social.suggest('GTA 6','elded',[(4,'carrera increíble'),(5,'carrera final'),(50,'fuera del clip')],0,10)
        self.assertEqual(set(data['platforms']),set(social.PLATFORMS))
        self.assertEqual(data['basis']['messages'],2)
        self.assertIn('#carrera',data['platforms']['tiktok']['hashtags'])
        self.assertNotIn('fuera',str(data['basis']))
        self.assertNotEqual(data['platforms']['youtube']['title'],data['platforms']['tiktok']['title'])
        self.assertNotIn('twitch',data['platforms'])
    def test_viral_hashtags_per_platform(self):
        data=social.suggest('GTA 6 ya','rubius',[(1,'puntos puntos'),(2,'puntos gano')],0,5)
        tt=data['platforms']['tiktok']['hashtags']
        self.assertIn('#fyp',tt)
        self.assertIn('#fy',tt)
        self.assertIn('#Shorts',data['platforms']['youtube']['hashtags'])
        self.assertIn('#Reels',data['platforms']['instagram']['hashtags'])
        kick=social.suggest('Directo','xqc',[],0,2,platform_source='kick')
        self.assertIn('#Kick',kick['platforms']['youtube']['hashtags'])
        self.assertIn('#kick',kick['platforms']['tiktok']['hashtags'])
    def test_ensure_platforms_drops_share_twitch(self):
        old={'platforms':{'twitch':{'title':'x'},'youtube':{'title':'a','description':'b','hashtags':'#x'}},'basis':{}}
        filled=social.ensure_platforms(old,'Directo','canal')
        self.assertNotIn('twitch',filled['platforms'])
        self.assertIn('tiktok',filled['platforms'])
        self.assertEqual(filled['platforms']['youtube']['title'],'a')
    def test_spam_not_counted_as_topic(self):
        data=social.suggest('Directo','canal',[(1,'spamtest')]*20,0,2)
        self.assertNotIn('spamtest',data['basis']['topics'])
    def test_edits_saved_independently(self):
        data=social.suggest('Directo','canal',[],0,2)
        data['platforms']['youtube']['title']='Mi título'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'clip1.mp4';path.write_bytes(b'video')
            target=social.save(path,data)
            self.assertEqual(json.loads(Path(target).read_text(encoding='utf-8'))['platforms']['youtube']['title'],'Mi título')
            self.assertEqual(path.read_bytes(),b'video')
            self.assertNotEqual(data['platforms']['tiktok']['title'],'Mi título')

if __name__=='__main__':unittest.main()
