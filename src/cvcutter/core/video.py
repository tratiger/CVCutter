from pathlib import Path
from typing import Optional

from moviepy import AudioFileClip, ColorClip, CompositeVideoClip, TextClip, VideoFileClip

from cvcutter.utils.exceptions import VideoProcessingError
from cvcutter.utils.logger import logger


class VideoProcessor:
    def __init__(self, use_gpu: bool = False):
        self.use_gpu = use_gpu

    def apply_audio(self, video_path: Path, new_audio_path: Path, output_path: Path) -> Path:
        """Replaces the audio track of the video with a new audio file."""
        logger.info(f"Applying new audio {new_audio_path} to {video_path}")
        try:
            with VideoFileClip(str(video_path)) as video, \
                 AudioFileClip(str(new_audio_path)) as new_audio:

                # Match duration if audio is shorter/longer
                final_audio = new_audio.with_duration(video.duration)
                final_video = video.with_audio(final_audio)

                kwargs = self._get_export_kwargs()
                final_video.write_videofile(str(output_path), **kwargs)
                return output_path
        except Exception as e:
            raise VideoProcessingError(f"Failed to apply audio: {e}")

    def render_clip(self, video_path: Path, output_path: Path, start_time: float, end_time: float,
                    telop_text: Optional[str] = None, telop_duration: float = 3.0) -> Path:
        """
        Extracts a segment of the video.
        Optionally adds a telop (text overlay) at the beginning of the clip.
        """
        logger.info(f"Rendering clip from {start_time}s to {end_time}s. Telop: {telop_text}")
        try:
            with VideoFileClip(str(video_path)) as video:
                # Use subclipped instead of subclip in moviepy 2.0+
                clip = video.subclipped(start_time, end_time)

                if telop_text:
                    # Create text clip
                    txt_clip = TextClip(
                        font="Arial", text=telop_text, font_size=70, color='white',
                        bg_color='black', method='caption', size=(clip.size[0] - 100, None)
                    ).with_position('center').with_duration(telop_duration)

                    # Add a semi-transparent background for text
                    bg_clip = ColorClip(size=clip.size, color=(0,0,0)).with_opacity(0.5).with_duration(telop_duration)

                    # Composite
                    telop_group = CompositeVideoClip([bg_clip, txt_clip]).with_position('center')
                    clip = CompositeVideoClip([clip, telop_group])

                kwargs = self._get_export_kwargs()
                clip.write_videofile(str(output_path), **kwargs)
                return output_path
        except Exception as e:
            raise VideoProcessingError(f"Failed to render clip: {e}")

    def _get_export_kwargs(self) -> dict:
        """Returns standard export arguments, utilizing GPU if configured."""
        kwargs = {
            "codec": "libx264",
            "audio_codec": "aac",
            "temp_audiofile": "temp-audio.m4a",
            "remove_temp": True,
            "logger": None # Disable moviepy progress bar to not clutter logs
        }
        if self.use_gpu:
            kwargs["codec"] = "h264_nvenc"
            kwargs["preset"] = "fast"
        return kwargs
