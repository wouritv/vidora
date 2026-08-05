"""
Tests unitaires pour la classe VideoEditor.

Lancer avec :
    pytest test_editor.py -v

Les appels externes (API Gemini, ffmpeg, ffprobe, système de fichiers)
sont mockés afin que les tests soient rapides, déterministes et ne
sont mockés afin que les tests soient rapides, déterministes et ne
nécessitent ni clé API réelle, ni binaire ffmpeg installé.
"""

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from editor import VideoEditor


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def editor():
    """
    Instancie VideoEditor avec un client Gemini mocké (on patche
    genai.Client pour éviter tout appel réseau réel à la construction).
    """
    with patch("editor.genai.Client") as mock_client_cls:
        mock_client_cls.return_value = MagicMock()
        ve = VideoEditor(api_key="fake-key")
        yield ve


def _make_genai_response(payload: dict, wrap_in_markdown: bool = False):
    """Construit un objet réponse Gemini factice avec .text = JSON string."""
    text = json.dumps(payload)
    if wrap_in_markdown:
        text = f"```json\n{text}\n```"
    mock_response = MagicMock()
    mock_response.text = text
    return mock_response


# ============================================================
# __init__
# ============================================================

class TestInit:
    def test_uses_env_model_if_set(self, monkeypatch):
        monkeypatch.setenv("GEMINI_MODEL", "gemini-custom-model")
        with patch("editor.genai.Client") as mock_client_cls:
            mock_client_cls.return_value = MagicMock()
            ve = VideoEditor(api_key="fake-key")
        assert ve.model_name == "gemini-custom-model"

    def test_defaults_to_flash_model_if_env_missing(self, monkeypatch):
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        with patch("editor.genai.Client") as mock_client_cls:
            mock_client_cls.return_value = MagicMock()
            ve = VideoEditor(api_key="fake-key")
        assert ve.model_name == "gemini-3.5-flash"

    def test_client_constructed_with_api_key(self):
        with patch("editor.genai.Client") as mock_client_cls:
            VideoEditor(api_key="my-secret-key")
        mock_client_cls.assert_called_once_with(api_key="my-secret-key")


# ============================================================
# upload_video
# ============================================================

class TestUploadVideo:
    def test_raises_if_file_does_not_exist(self, editor):
        with patch("editor.os.path.exists", return_value=False):
            with pytest.raises(FileNotFoundError):
                editor.upload_video("does_not_exist.mp4")

    def test_returns_file_upload_when_active_immediately(self, editor):
        fake_upload = MagicMock(name="fake-upload")
        fake_upload.name = "files/abc123"
        editor.client.files.upload.return_value = fake_upload

        fake_file_info = MagicMock()
        fake_file_info.state = "ACTIVE"
        editor.client.files.get.return_value = fake_file_info

        with patch("editor.os.path.exists", return_value=True):
            result = editor.upload_video("video.mp4")

        editor.client.files.upload.assert_called_once_with(file="video.mp4")
        assert result is fake_upload

    def test_polls_until_active(self, editor):
        fake_upload = MagicMock()
        fake_upload.name = "files/xyz"
        editor.client.files.upload.return_value = fake_upload

        processing_info = MagicMock()
        processing_info.state = "PROCESSING"
        active_info = MagicMock()
        active_info.state = "ACTIVE"

        editor.client.files.get.side_effect = [processing_info, processing_info, active_info]

        with patch("editor.os.path.exists", return_value=True), \
             patch("editor.time.sleep") as mock_sleep:
            result = editor.upload_video("video.mp4")

        assert result is fake_upload
        assert editor.client.files.get.call_count == 3
        assert mock_sleep.call_count == 2  # sleep entre chaque poll non-actif

    def test_raises_if_processing_failed(self, editor):
        fake_upload = MagicMock()
        fake_upload.name = "files/failed"
        editor.client.files.upload.return_value = fake_upload

        failed_info = MagicMock()
        failed_info.state = "FAILED"
        editor.client.files.get.return_value = failed_info

        with patch("editor.os.path.exists", return_value=True):
            with pytest.raises(Exception, match="Video processing failed"):
                editor.upload_video("video.mp4")

    def test_reraises_upload_api_error(self, editor):
        editor.client.files.upload.side_effect = RuntimeError("network down")

        with patch("editor.os.path.exists", return_value=True):
            with pytest.raises(RuntimeError, match="network down"):
                editor.upload_video("video.mp4")


# ============================================================
# get_ffmpeg_filter
# ============================================================

class TestGetFfmpegFilter:
    def test_returns_parsed_json_on_valid_response(self, editor):
        payload = {"filter_string": "eq=contrast=1.2:enable='between(t,0,3)'"}
        editor.client.models.generate_content.return_value = _make_genai_response(payload)

        result = editor.get_ffmpeg_filter(
            video_file_obj=MagicMock(), duration=10.0, fps=30, width=1080, height=1920
        )

        assert result == payload

    def test_strips_markdown_code_fences(self, editor):
        payload = {"filter_string": "hue=s=0"}
        editor.client.models.generate_content.return_value = _make_genai_response(
            payload, wrap_in_markdown=True
        )

        result = editor.get_ffmpeg_filter(
            video_file_obj=MagicMock(), duration=5.0
        )

        assert result == payload

    def test_extracts_json_with_surrounding_noise(self, editor):
        payload = {"filter_string": "unsharp=5:5:1.0"}
        mock_response = MagicMock()
        mock_response.text = f"Here you go:\n{json.dumps(payload)}\nHope that helps!"
        editor.client.models.generate_content.return_value = mock_response

        result = editor.get_ffmpeg_filter(video_file_obj=MagicMock(), duration=5.0)

        assert result == payload

    def test_returns_none_on_invalid_json(self, editor):
        mock_response = MagicMock()
        mock_response.text = "this is not json at all"
        editor.client.models.generate_content.return_value = mock_response

        result = editor.get_ffmpeg_filter(video_file_obj=MagicMock(), duration=5.0)

        assert result is None

    def test_uses_default_resolution_when_not_provided(self, editor):
        payload = {"filter_string": "eq=contrast=1.1"}
        editor.client.models.generate_content.return_value = _make_genai_response(payload)

        editor.get_ffmpeg_filter(video_file_obj=MagicMock(), duration=5.0)

        # Vérifie que le prompt envoyé mentionne bien la résolution par défaut 1080x1920
        _, kwargs = editor.client.models.generate_content.call_args
        prompt_text = kwargs["contents"][1]
        assert "1080x1920" in prompt_text

    def test_passes_custom_resolution_into_prompt(self, editor):
        payload = {"filter_string": "eq=contrast=1.1"}
        editor.client.models.generate_content.return_value = _make_genai_response(payload)

        editor.get_ffmpeg_filter(video_file_obj=MagicMock(), duration=5.0, width=720, height=1280)

        _, kwargs = editor.client.models.generate_content.call_args
        prompt_text = kwargs["contents"][1]
        assert "720x1280" in prompt_text

    def test_passes_transcript_into_prompt(self, editor):
        payload = {"filter_string": "eq=contrast=1.1"}
        editor.client.models.generate_content.return_value = _make_genai_response(payload)

        transcript = [{"start": 0, "text": "Hello world"}]
        editor.get_ffmpeg_filter(video_file_obj=MagicMock(), duration=5.0, transcript=transcript)

        _, kwargs = editor.client.models.generate_content.call_args
        prompt_text = kwargs["contents"][1]
        assert "Hello world" in prompt_text

    def test_uses_configured_model_name(self, editor):
        payload = {"filter_string": "eq=contrast=1.1"}
        editor.client.models.generate_content.return_value = _make_genai_response(payload)
        editor.model_name = "my-test-model"

        editor.get_ffmpeg_filter(video_file_obj=MagicMock(), duration=5.0)

        _, kwargs = editor.client.models.generate_content.call_args
        assert kwargs["model"] == "my-test-model"


# ============================================================
# get_effects_config
# ============================================================

class TestGetEffectsConfig:
    def test_returns_parsed_json_on_valid_response(self, editor):
        payload = {
            "segments": [
                {
                    "startSec": 0, "endSec": 3.5, "zoom": 1.1,
                    "zoomCenterX": 0.5, "zoomCenterY": 0.5,
                    "brightness": 1.0, "contrast": 1.0, "saturate": 1.0,
                }
            ]
        }
        editor.client.models.generate_content.return_value = _make_genai_response(payload)

        result = editor.get_effects_config(video_file_obj=MagicMock(), duration=3.5)

        assert result == payload

    def test_strips_markdown_code_fences(self, editor):
        payload = {"segments": []}
        editor.client.models.generate_content.return_value = _make_genai_response(
            payload, wrap_in_markdown=True
        )

        result = editor.get_effects_config(video_file_obj=MagicMock(), duration=1.0)

        assert result == payload

    def test_returns_none_on_invalid_json(self, editor):
        mock_response = MagicMock()
        mock_response.text = "not valid json {{{"
        editor.client.models.generate_content.return_value = mock_response

        result = editor.get_effects_config(video_file_obj=MagicMock(), duration=1.0)

        assert result is None

    def test_default_resolution_in_prompt(self, editor):
        payload = {"segments": []}
        editor.client.models.generate_content.return_value = _make_genai_response(payload)

        editor.get_effects_config(video_file_obj=MagicMock(), duration=1.0)

        _, kwargs = editor.client.models.generate_content.call_args
        prompt_text = kwargs["contents"][1]
        assert "1080x1920" in prompt_text


# ============================================================
# _split_filter_chain (méthode statique, logique pure)
# ============================================================

class TestSplitFilterChain:
    def test_splits_simple_comma_separated_filters(self):
        result = VideoEditor._split_filter_chain("eq=contrast=1.2,hue=s=0")
        assert result == ["eq=contrast=1.2", "hue=s=0"]

    def test_respects_quoted_commas(self):
        # Une virgule DANS une expression entre quotes ne doit pas splitter.
        filter_str = "zoompan=z='1.1*between(on,0,75)+1.3*between(on,76,150)':s=1080x1920,setsar=1"
        result = VideoEditor._split_filter_chain(filter_str)
        assert len(result) == 2
        assert result[0].startswith("zoompan=")
        assert result[1] == "setsar=1"

    def test_single_filter_no_comma(self):
        result = VideoEditor._split_filter_chain("eq=contrast=1.2")
        assert result == ["eq=contrast=1.2"]

    def test_empty_string(self):
        result = VideoEditor._split_filter_chain("")
        assert result == [""]

    def test_multiple_quoted_sections(self):
        filter_str = "eq=contrast='between(t,0,3)':enable='between(t,0,3)',hue=s=0"
        result = VideoEditor._split_filter_chain(filter_str)
        assert len(result) == 2

    def test_trailing_comma_produces_empty_last_part(self):
        result = VideoEditor._split_filter_chain("eq=contrast=1.2,")
        assert result == ["eq=contrast=1.2", ""]


# ============================================================
# _enforce_zoompan_output_size
# ============================================================

class TestEnforceZoompanOutputSize:
    def test_adds_size_when_missing(self):
        filter_str = "zoompan=z='1.1':fps=30:d=1"
        result = VideoEditor._enforce_zoompan_output_size(filter_str, 1080, 1920)
        assert result == "zoompan=z='1.1':fps=30:d=1:s=1080x1920"

    def test_replaces_existing_wrong_size(self):
        filter_str = "zoompan=z='1.1':s=1280x720:fps=30"
        result = VideoEditor._enforce_zoompan_output_size(filter_str, 1080, 1920)
        assert ":s=1080x1920" in result
        assert "1280x720" not in result

    def test_leaves_non_zoompan_filters_untouched(self):
        filter_str = "eq=contrast=1.2,hue=s=0"
        result = VideoEditor._enforce_zoompan_output_size(filter_str, 1080, 1920)
        assert result == filter_str

    def test_handles_multiple_zoompan_in_chain(self):
        filter_str = "zoompan=z='1.1':s=100x100,eq=contrast=1.2,zoompan=z='1.3':s=200x200"
        result = VideoEditor._enforce_zoompan_output_size(filter_str, 1080, 1920)
        assert result.count(":s=1080x1920") == 2
        assert "100x100" not in result
        assert "200x200" not in result

    def test_preserves_quoted_commas_while_enforcing(self):
        filter_str = "zoompan=z='1.1*between(on,0,75)+1.3*between(on,76,150)':fps=30:d=1"
        result = VideoEditor._enforce_zoompan_output_size(filter_str, 1080, 1920)
        # La quote contient une virgule mais ne doit pas être coupée
        assert "between(on,0,75)" in result
        assert result.endswith(":s=1080x1920")


# ============================================================
# _sanitize_filter_string
# ============================================================

class TestSanitizeFilterString:
    def test_converts_less_than(self):
        result = VideoEditor._sanitize_filter_string("enable='t<3'")
        assert result == "enable='lt(t,3)'"

    def test_converts_greater_than(self):
        result = VideoEditor._sanitize_filter_string("enable='on>75'")
        assert result == "enable='gt(on,75)'"

    def test_converts_greater_equal(self):
        result = VideoEditor._sanitize_filter_string("enable='on>=75'")
        assert result == "enable='gte(on,75)'"

    def test_converts_less_equal(self):
        result = VideoEditor._sanitize_filter_string("enable='t<=3.5'")
        assert result == "enable='lte(t,3.5)'"

    def test_does_not_break_already_safe_expressions(self):
        s = "eq=contrast=1.2:enable='between(t,0,3)'"
        result = VideoEditor._sanitize_filter_string(s)
        assert result == s  # rien à changer

    def test_handles_multiple_operators_in_one_string(self):
        s = "enable='t>3'and enable='on<=150'"
        result = VideoEditor._sanitize_filter_string(s)
        assert "gt(t,3)" in result
        assert "lte(on,150)" in result

    def test_handles_negative_and_decimal_numbers(self):
        result = VideoEditor._sanitize_filter_string("x='y<-1.5'")
        assert result == "x='lt(y,-1.5)'"

    def test_does_not_match_gte_style_word_incorrectly(self):
        # S'assure qu'on ne casse pas des identifiants contenant déjà '>=' ailleurs
        s = "gte(on,75)"
        result = VideoEditor._sanitize_filter_string(s)
        assert result == s


# ============================================================
# apply_edits
# ============================================================

class TestApplyEdits:
    def test_copies_original_when_no_filter_data(self, editor):
        with patch("editor.subprocess.run") as mock_run:
            editor.apply_edits("in.mp4", "out.mp4", filter_data=None)

        mock_run.assert_called_once_with(
            ['ffmpeg', '-y', '-i', 'in.mp4', '-c', 'copy', 'out.mp4']
        )

    def test_copies_original_when_filter_string_key_missing(self, editor):
        with patch("editor.subprocess.run") as mock_run:
            editor.apply_edits("in.mp4", "out.mp4", filter_data={"something_else": "x"})

        mock_run.assert_called_once_with(
            ['ffmpeg', '-y', '-i', 'in.mp4', '-c', 'copy', 'out.mp4']
        )

    def test_runs_ffmpeg_with_filter_when_probe_succeeds(self, editor):
        filter_data = {"filter_string": "eq=contrast=1.2"}

        with patch("editor.subprocess.check_output", return_value=b"1080x1920\n"), \
             patch("editor.subprocess.run") as mock_run:
            editor.apply_edits("in.mp4", "out.mp4", filter_data)

        assert mock_run.called
        args, kwargs = mock_run.call_args
        cmd_bytes = args[0]
        # Les arguments sont encodés en bytes utf-8, on les décode pour vérifier
        cmd = [a.decode("utf-8") for a in cmd_bytes]
        assert cmd[0] == "ffmpeg"
        assert "-vf" in cmd
        vf_index = cmd.index("-vf") + 1
        # setsar=1 doit avoir été ajouté puisque probe a réussi et setsar absent
        assert "setsar=1" in cmd[vf_index]
        assert kwargs["check"] is True

    def test_falls_back_to_no_geometry_enforcement_when_probe_fails(self, editor):
        filter_data = {"filter_string": "eq=contrast=1.2"}

        with patch("editor.subprocess.check_output", side_effect=Exception("ffprobe missing")), \
             patch("editor.subprocess.run") as mock_run:
            editor.apply_edits("in.mp4", "out.mp4", filter_data)

        args, _ = mock_run.call_args
        cmd = [a.decode("utf-8") for a in args[0]]
        vf_index = cmd.index("-vf") + 1
        # Pas de probe réussie -> pas de setsar ajouté automatiquement
        assert "setsar=1" not in cmd[vf_index]
        assert cmd[vf_index] == "eq=contrast=1.2"

    def test_sanitizes_comparison_operators_before_running(self, editor):
        filter_data = {"filter_string": "enable='t<3'"}

        with patch("editor.subprocess.check_output", side_effect=Exception("no ffprobe")), \
             patch("editor.subprocess.run") as mock_run:
            editor.apply_edits("in.mp4", "out.mp4", filter_data)

        args, _ = mock_run.call_args
        cmd = [a.decode("utf-8") for a in args[0]]
        vf_index = cmd.index("-vf") + 1
        assert "lt(t,3)" in cmd[vf_index]
        assert "t<3" not in cmd[vf_index]

    def test_enforces_zoompan_size_using_probed_resolution(self, editor):
        filter_data = {"filter_string": "zoompan=z='1.1':fps=30:d=1"}

        with patch("editor.subprocess.check_output", return_value=b"720x1280\n"), \
             patch("editor.subprocess.run") as mock_run:
            editor.apply_edits("in.mp4", "out.mp4", filter_data)

        args, _ = mock_run.call_args
        cmd = [a.decode("utf-8") for a in args[0]]
        vf_index = cmd.index("-vf") + 1
        assert ":s=720x1280" in cmd[vf_index]

    def test_does_not_duplicate_setsar_if_already_present(self, editor):
        filter_data = {"filter_string": "eq=contrast=1.2,setsar=1"}

        with patch("editor.subprocess.check_output", return_value=b"1080x1920\n"), \
             patch("editor.subprocess.run") as mock_run:
            editor.apply_edits("in.mp4", "out.mp4", filter_data)

        args, _ = mock_run.call_args
        cmd = [a.decode("utf-8") for a in args[0]]
        vf_index = cmd.index("-vf") + 1
        assert cmd[vf_index].count("setsar=1") == 1

    def test_raises_when_ffmpeg_execution_fails(self, editor):
        filter_data = {"filter_string": "eq=contrast=1.2"}

        with patch("editor.subprocess.check_output", return_value=b"1080x1920\n"), \
             patch(
                 "editor.subprocess.run",
                 side_effect=subprocess.CalledProcessError(1, "ffmpeg"),
             ):
            with pytest.raises(subprocess.CalledProcessError):
                editor.apply_edits("in.mp4", "out.mp4", filter_data)

    def test_output_command_includes_expected_codec_flags(self, editor):
        filter_data = {"filter_string": "eq=contrast=1.2"}

        with patch("editor.subprocess.check_output", return_value=b"1080x1920\n"), \
             patch("editor.subprocess.run") as mock_run:
            editor.apply_edits("in.mp4", "out.mp4", filter_data)

        args, _ = mock_run.call_args
        cmd = [a.decode("utf-8") for a in args[0]]
        assert "libx264" in cmd
        assert "copy" in cmd  # audio copy
        assert "-crf" in cmd
        assert "22" in cmd


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))