import unittest
from unittest.mock import patch
from peakclip.platforms import channel
from peakclip.api import API

class Links(unittest.TestCase):
    def test_video_forms(self):
        for value in ['123456','https://www.twitch.tv/videos/123456?t=20s','twitch.tv/videos/123456/']:
            self.assertEqual(channel.parse_link(value),('twitch','video','123456'))
    def test_channel_forms(self):
        for value in ['https://twitch.tv/Twitch','twitch.tv/twitch/videos']:
            self.assertEqual(channel.parse_link(value),('twitch','channel','twitch'))
    def test_kick_forms(self):
        uuid='371f0495-9aaa-4e7a-b88e-22b50c6194b0'
        self.assertEqual(channel.parse_link('https://kick.com/xqc'),('kick','channel','xqc'))
        self.assertEqual(channel.parse_link(f'https://kick.com/xqc/videos/{uuid}'),('kick','video',uuid))
        self.assertEqual(channel.parse_link(uuid),('kick','video',uuid))
    def test_bad_inputs(self):
        for value in ['C:\\Videos','https://twitch.tv.evil.com/test','https://example.com','https://twitch.tv/directory']:
            with self.assertRaises(ValueError): channel.parse_link(value)
    def test_channel_cannot_start_download(self):
        api=API()
        with patch('peakclip.api.threading.Thread') as thread:
            self.assertFalse(api.start({'url':'https://twitch.tv/twitch','count':10,'minimum':3,'before':20,'after':15,'folder':'','folder_mode':'stream'}))
            thread.assert_not_called()
            self.assertIn('grabación',api.status()['message'])
    def test_kick_video_can_start(self):
        api=API()
        with patch('peakclip.api.threading.Thread') as thread:
            ok=api.start({
                'url':'https://kick.com/xqc/videos/371f0495-9aaa-4e7a-b88e-22b50c6194b0',
                'count':3,'minimum':3,'before':20,'after':15,'folder':'','folder_mode':'stream','cut':False,
            })
            self.assertTrue(ok)
            thread.assert_called_once()
            args=thread.call_args.kwargs.get('args') or thread.call_args[1].get('args') or thread.call_args[0][1:]
            # work(platform, vod, options, resume=False)
            self.assertEqual(args[0],'kick')
            self.assertEqual(args[1],'371f0495-9aaa-4e7a-b88e-22b50c6194b0')

    def test_metadata_failure(self):
        with patch('peakclip.api.channel.inspect',side_effect=TimeoutError):
            self.assertFalse(API().inspect_link('twitch.tv/twitch')['ok'])

if __name__=='__main__': unittest.main()
