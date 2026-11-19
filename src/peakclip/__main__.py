if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--transcribe-worker':
        from peakclip.infrastructure.whisper_worker import main
        try:
            main(sys.argv[2:])
        except Exception as exc:
            import json, traceback
            from pathlib import Path
            Path(sys.argv[3]).write_text(json.dumps({'error':str(exc),'detail':traceback.format_exc()}),encoding='utf-8')
            sys.exit(1)
    else:
        from peakclip.app import run
        run()
