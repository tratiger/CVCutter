from pathlib import Path
from typing import List

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from sqlalchemy.orm import Session

from cvcutter.core.analysis import MultimodalAnalyzer
from cvcutter.core.audio import AudioProcessor
from cvcutter.core.video import VideoProcessor
from cvcutter.data.external import MetadataService
from cvcutter.data.models import Performance, Project, ProjectStatus
from cvcutter.utils.exceptions import CVCutterError
from cvcutter.utils.logger import logger


class PipelineOrchestrator:
    def __init__(self, session: Session, meta_service: MetadataService):
        self.session = session
        self.meta_service = meta_service
        self.audio_proc = AudioProcessor()
        self.video_proc = VideoProcessor()
        self.analyzer = MultimodalAnalyzer()

    def sync_and_mix_audio(self, project: Project, offset_sec: float, video_vol: float, mic_vol: float) -> str:
        """Step 1: Sync Audio"""
        if str(project.video_path) in ["None", ""] or str(project.audio_path) in ["None", ""]:
            raise CVCutterError("Project must have video and audio paths set.")

        logger.info(f"Orchestrating audio sync for {project.name}")
        out_audio = Path(str(project.output_dir)) / f"{project.name}_mixed_audio.wav"


        self.audio_proc.mix_audio(
            Path(str(project.video_path)), Path(str(project.audio_path)), out_audio,
            video_vol=video_vol, mic_vol=mic_vol, offset_sec=offset_sec
        )

        out_video = Path(str(project.output_dir)) / f"{project.name}_master.mp4"
        self.video_proc.apply_audio(Path(str(project.video_path)), out_audio, out_video)


        out_video = Path(str(project.output_dir)) / f"{project.name}_master.mp4"
        self.video_proc.apply_audio(Path(str(project.video_path)), out_audio, out_video)

        project.video_path = str(out_video) # type: ignore
        project.status = ProjectStatus.AUDIO_SYNCED # type: ignore
        self.session.commit()
        return str(out_video)

    def analyze_video(self, project: Project) -> List[tuple[float, float]]:
        """Step 2: Detect clapping & bowing to suggest segments"""
        logger.info(f"Analyzing video for {project.name}")


        if project.status.value not in [ProjectStatus.AUDIO_SYNCED.value, ProjectStatus.CREATED.value]: # type: ignore
            logger.warning("Project not in correct state, but analyzing anyway.")

        if str(project.video_path) in ["None", ""]:
            raise CVCutterError("No video path provided for analysis.")

        if str(project.video_path) in ["None", ""]:
            raise CVCutterError("No video path provided for analysis.")

        # Ensure we are passing a WAV file to librosa
        out_audio = Path(str(project.output_dir)) / f"{project.name}_mixed_audio.wav"
        if out_audio.exists():
            analysis_audio = out_audio
        else:
            # User skipped sync, we need to extract audio from the video source for analysis
            logger.info("No mixed audio found. Extracting audio track from video for analysis.")
            analysis_audio = Path(str(project.output_dir)) / f"{project.name}_extracted_audio.wav"
            self.audio_proc.extract_audio_from_video(Path(str(project.video_path)), analysis_audio)

        import librosa
        audio_duration = librosa.get_duration(path=str(analysis_audio))

        clapping = self.analyzer.detect_clapping(analysis_audio)
        silences = self.analyzer.detect_silence(analysis_audio)

        logger.info(f"Clapping segments: {clapping}")
        logger.info(f"Silence segments: {silences}")

        # Determine performances using the multimodal logic (silence/clapping indicates gaps)
        segments = []
        non_silences = []
        current_t = 0.0

        for s_start, s_end in silences:
            if s_start - current_t > 20.0: # Minimum performance duration
                non_silences.append((current_t, s_start))
            current_t = s_end

        if audio_duration - current_t > 20.0:
            non_silences.append((current_t, audio_duration))

        segments = non_silences

        # Optional: Log bowing if possible, but rely on audio features
        try:
            bowing_timestamps = self.analyzer.detect_bowing(Path(str(project.video_path)))
            logger.info(f"Bowing timestamps (for reference): {bowing_timestamps}")
        except Exception:
            pass

        if not segments:
            # Fallback
            segments = clapping if clapping else [(0.0, 10.0)]

        project.status = ProjectStatus.VIDEO_ANALYZED # type: ignore
        self.session.commit()
        return segments

    def generate_mapping(self, project: Project, segments: List[tuple[float, float]], api_key: str):
        """Step 3: Map PDF to segments"""
        logger.info(f"Generating mapping for {project.name}")

        program = []
        if str(project.pdf_path) not in ["None", ""]:
            parsed = self.meta_service.parse_pdf_program(Path(str(project.pdf_path)), api_key)
            if parsed:
                program = parsed

        if not program:
            program = [{"title": f"Performance {i+1}", "performer": "Unknown"} for i in range(len(segments))]

        mapped = self.meta_service.map_performances(program, segments, [])

        self.session.query(Performance).filter_by(project_id=project.id).delete()

        for m in mapped:
            perf = Performance(
                title=m['title'], performer=m['performer'],
                start_time=m['start_time'], end_time=m['end_time'],
                project_id=project.id
            )
            self.session.add(perf)


        project.status = ProjectStatus.MAPPED # type: ignore
        self.session.commit()

    def render_all(self, project: Project, apply_telop: bool = True):
        """Step 4: Render Subclips"""
        logger.info(f"Rendering all subclips for {project.name}")
        for idx, perf in enumerate(project.performances):
            out_file = Path(str(project.output_dir)) / f"{idx+1:02d}_{perf.performer}_{perf.title}.mp4"
            telop = f"{perf.performer}\n{perf.title}" if apply_telop else None

            self.video_proc.render_clip(
                Path(str(project.video_path)), out_file, perf.start_time, perf.end_time, telop_text=telop # type: ignore
            )


        project.status = ProjectStatus.RENDERED # type: ignore
        self.session.commit()

    def upload_pending(self, project: Project):
        """Step 5: Upload to YouTube"""
        logger.info(f"Uploading pending clips for {project.name}")
        if not self.meta_service.creds:
            self.meta_service.authenticate()

        youtube = build('youtube', 'v3', credentials=self.meta_service.creds)

        for idx, perf in enumerate(project.performances):
            if perf.is_uploaded:
                continue


            out_file = Path(str(project.output_dir)) / f"{idx+1:02d}_{perf.performer}_{perf.title}.mp4"
            if not out_file.exists():
                logger.error(f"Cannot upload {out_file}, file not found")
                continue

            body = {
                'snippet': {
                    'title': f"{perf.title} - {perf.performer}",
                    'description': perf.description or "Concert Performance",
                    'categoryId': '10' # Music
                },
                'status': {
                    'privacyStatus': 'public' if perf.is_public else 'unlisted'
                }
            }

            try:
                logger.info(f"Uploading {out_file.name} to YouTube...")
                media = MediaFileUpload(str(out_file), chunksize=-1, resumable=True)
                request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)
                response = request.execute()


                perf.youtube_url = f"https://youtu.be/{response['id']}" # type: ignore
                perf.is_uploaded = True # type: ignore
                self.session.commit()
            except Exception as e:
                logger.error(f"Upload failed for {perf.title}: {e}")


        project.status = ProjectStatus.UPLOADED # type: ignore
        self.session.commit()
