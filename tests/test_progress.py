import unittest
from peakclip.domain.progress import telemetry

class Progress(unittest.TestCase):
    def test_encoder_progress(self):
        self.assertEqual(telemetry('out_time_us=5000000','encode',10)['stage_progress'],50)
        self.assertEqual(telemetry('out_time_us=15000000','encode',10)['stage_progress'],100)
        self.assertEqual(telemetry('out_time_us=N/A','encode',10),{})
    def test_downloader_progress(self):
        result=telemetry('[download]  45.2% of 100MiB at 2.00MiB/s ETA 00:12','download')
        self.assertEqual(result,{'stage_progress':45.2,'speed':'2.00MiB/s','eta':'00:12'})
        self.assertEqual(telemetry('[STATUS] - Downloading 75%','chat')['stage_progress'],75)
    def test_unknown_is_not_invented(self):
        self.assertEqual(telemetry('Connecting to Twitch','download'),{})

if __name__=='__main__': unittest.main()
