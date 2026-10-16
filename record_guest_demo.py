"""Record the local guest workflow as a narrated MP4.

Install once: py -3 -m pip install playwright imageio-ffmpeg
Run:          py -3 record_guest_demo.py
Rehearse:     py -3 record_guest_demo.py --dry-run --quick --headless --no-voice
"""

from __future__ import annotations

import argparse
import base64
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from playwright.sync_api import Page, sync_playwright


ROOT = Path(__file__).resolve().parent
FRONTEND = "http://127.0.0.1:5173"
BACKEND_HEALTH = "http://127.0.0.1:8000/api/health"
DEFAULT_OUTPUT = ROOT / "演示视频" / "棚智未来_游客模式演示.mp4"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

QUESTION = (
    "游客体验番茄棚的病害时间机显示：灰霉病风险当前42%，72小时后66%，"
    "主要影响因素是连续高湿和昼夜温差。请简要说明应先进行哪些人工检查。"
)
TASK_PROMPT = (
    "请在游客体验番茄棚创建一条高优先级农事任务："
    "检查通风设备并观察番茄叶面结露情况。只创建任务，不控制设备。"
)


@dataclass(frozen=True)
class Scene:
    name: str
    seconds: float
    narration: str


SCENES = [
    Scene("游客入口", 20, "这是棚智未来设施农业生产决策平台。下面使用游客模式，演示从风险信息到智能问答和农事任务创建的完整流程。游客体验无需登录，数据不会存档。"),
    Scene("种植总览", 27, "当前展示的是游客体验番茄棚。页面汇总温度、湿度、二十四小时趋势和待处理任务。这里的数据是为演示准备的示例数据，重点是让管理人员在一个入口看到棚室状态和工作重点。"),
    Scene("大棚管理", 21, "在大棚管理中，可以查看番茄棚和甜瓜棚的档案，也能看到文件导入与设备接口两种数据接入方式。正式使用时，数据经过校验后进入后续分析流程。"),
    Scene("三维沙盘", 18, "三维沙盘把棚室空间和环境摘要放在同一画面。这里展示的是体验数据对应的数字孪生视图，便于快速定位棚室及其当前关注点。"),
    Scene("病害风险", 30, "病害时间机给出一个风险推演：灰霉病风险从当前的百分之四十二上升到七十二小时后的百分之六十六。页面同时列出连续高湿和昼夜温差等影响因素。它提示需要巡检，不代表已经确诊。"),
    Scene("生产建议", 24, "进入生产工作台，可以看到夜间湿度偏高的预警、可解释的处置建议，以及已有农事任务。系统提出分段通风和复测思路，但是否执行，仍由现场人员结合天气和设备情况决定。"),
    Scene("棚小智分析", 38, "现在我把刚才看到的演示风险信息交给棚小智，请它分析应先检查什么。棚小智接收自然语言请求后，结合我提供的场景信息整理巡检重点，并返回建议。这里没有把模型回答当成现场诊断。"),
    Scene("棚小智建任务", 44, "接着，我明确要求它创建一条高优先级农事任务。棚小智识别目标大棚、任务名称和优先级，调用平台受控的任务创建流程。现在页面反馈创建成功；它创建的是待人工处理的任务，没有自动操作任何设备。"),
    Scene("任务模块核对", 44, "这条任务已经出现在任务中心，说明对话结果进入了业务模块，而不只是生成一段文字。任务描述包含通风设备检查和叶面结露观察，状态为待提交；后续可以由人员审核、分派、执行和反馈。"),
    Scene("游客数据不存档", 17, "最后刷新页面。刚才新建的任务不再保留，说明游客模式只提供临时体验。正式账号下的业务数据则由后端按组织权限保存。"),
    Scene("结语", 7, "棚智未来把风险信息、智能辅助和现场任务连成一条可操作的工作链。"),
]


def _http_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return 200 <= response.status < 400
    except (urllib.error.URLError, TimeoutError):
        return False


def ensure_services() -> None:
    front = _http_ready(FRONTEND)
    back = _http_ready(BACKEND_HEALTH)
    if front and back:
        print("本地前后端已就绪。")
        return
    if front != back:
        raise RuntimeError("本地只启动了一项服务，请先检查 5173 和 8000 端口并运行 start_all.ps1。")
    print("本地服务尚未运行，正在启动前后端……")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "start_all.ps1")],
        cwd=ROOT, capture_output=True, text=True, timeout=120, check=False,
    )
    if result.returncode or not (_http_ready(FRONTEND) and _http_ready(BACKEND_HEALTH)):
        raise RuntimeError(f"本地服务启动失败：{result.stderr[-1000:] or result.stdout[-1000:]}")


def synthesize_voice(text: str, output: Path) -> float:
    def quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.SelectVoice('Microsoft Huihui Desktop'); $s.Rate = 1; "
        f"$s.SetOutputToWaveFile({quote(str(output))}); "
        f"$s.Speak({quote(text)}); $s.Dispose()"
    )
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    result = subprocess.run(
        ["powershell", "-NoProfile", "-EncodedCommand", encoded],
        capture_output=True, text=True, timeout=90, check=False,
    )
    if result.returncode or not output.is_file():
        raise RuntimeError("中文旁白生成失败；请检查 Windows 是否安装 Microsoft Huihui Desktop 语音。")
    with wave.open(str(output), "rb") as wav:
        return wav.getnframes() / wav.getframerate()


def build_narration(scene_starts: list[float], voice_files: list[Path], output: Path, duration: float) -> None:
    with wave.open(str(voice_files[0]), "rb") as first:
        params = first.getparams()
    frame_size = params.nchannels * params.sampwidth
    frames = bytearray(int((duration + 3) * params.framerate) * frame_size)
    for start, voice_file in zip(scene_starts, voice_files, strict=True):
        with wave.open(str(voice_file), "rb") as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (
                params.nchannels, params.sampwidth, params.framerate
            ):
                raise RuntimeError("旁白 WAV 格式不一致，无法合并。")
            voice = wav.readframes(wav.getnframes())
        offset = int((start + 0.5) * params.framerate) * frame_size
        frames[offset:offset + len(voice)] = voice
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(params.nchannels)
        wav.setsampwidth(params.sampwidth)
        wav.setframerate(params.framerate)
        wav.writeframes(frames)


def navigate(page: Page, label: str, expected: str) -> None:
    page.get_by_role("menuitem", name=label).click()
    page.wait_for_url(re.compile(r"/platform/" + re.escape(expected) + r"(?:\?|$)"), timeout=30_000)


def scroll_to(page: Page, text: str) -> None:
    page.get_by_text(text, exact=False).first.scroll_into_view_if_needed(timeout=15_000)


def run_workflow(page: Page, quick: bool, voice_durations: list[float], spoken: bool) -> tuple[list[float], float]:
    scene_starts: list[float] = []
    started = time.monotonic()
    created_title = ""

    def scene(index: int, action: Callable[[], None]) -> None:
        current = SCENES[index]
        scene_starts.append(time.monotonic() - started)
        print(f"[{index + 1:02d}/{len(SCENES)}] {current.name}", flush=True)
        action()
        minimum = 1.2 if quick else current.seconds
        if spoken:
            minimum = max(minimum, voice_durations[index] + 1.4)
        elapsed = time.monotonic() - started - scene_starts[-1]
        if elapsed < minimum:
            page.wait_for_timeout(int((minimum - elapsed) * 1000))

    def entrance() -> None:
        page.goto(FRONTEND + "/home", wait_until="domcontentloaded", timeout=60_000)
        page.get_by_role("link", name="游客模式").click()
        page.wait_for_url(re.compile(r"/platform\?mode=guest"), timeout=30_000)
        page.get_by_role("button", name="打开棚小智").wait_for(timeout=30_000)

    scene(0, entrance)

    def dashboard() -> None:
        scroll_to(page, "24 小时环境趋势")
        if not page.get_by_text("24.0", exact=False).count():
            raise RuntimeError("游客驾驶舱的环境演示数据未出现。")
        page.mouse.move(790, 340)

    scene(1, dashboard)

    def greenhouse() -> None:
        navigate(page, "大棚管理", "data")
        scroll_to(page, "大棚资产与连接状态")
        page.get_by_text("游客体验甜瓜棚", exact=False).first.wait_for(timeout=20_000)
        page.mouse.move(700, 430)

    scene(2, greenhouse)

    def sandbox_3d() -> None:
        navigate(page, "3D决策沙盘", "3d")
        page.locator("canvas").wait_for(timeout=30_000)
        page.get_by_text("数字孪生态势", exact=False).first.wait_for(timeout=30_000)
        page.mouse.move(820, 420)

    scene(3, sandbox_3d)

    def disease_risk() -> None:
        navigate(page, "病害时间机", "disease-time-machine")
        page.get_by_text("灰霉病", exact=False).first.wait_for(timeout=30_000)
        scroll_to(page, "风险为什么会上升")
        page.mouse.move(710, 420)

    scene(4, disease_risk)

    def production() -> None:
        navigate(page, "农事任务", "production")
        page.get_by_text("今日农事中心").wait_for(timeout=30_000)
        scroll_to(page, "分段通风并复测湿度")
        page.mouse.move(950, 480)

    scene(5, production)

    def ask_question() -> None:
        page.get_by_role("button", name="打开棚小智").click()
        page.get_by_role("button", name="开始通用问答").click()
        field = page.get_by_placeholder("问棚小智一个问题，Enter发送，Shift+Enter换行")
        field.fill(QUESTION)
        with page.expect_response(lambda r: r.url.endswith("/api/guest/ai/chat"), timeout=90_000) as response:
            page.get_by_role("button", name="发送").click()
        result = response.value
        data = result.json()
        if result.status != 200 or not data.get("reply") or data.get("actions"):
            raise RuntimeError(f"棚小智分析未成功，HTTP {result.status}。请确认本地模型服务。")
        answer = page.locator(".agent-message.assistant .agent-message-content").last
        answer.wait_for(timeout=15_000)
        if len(answer.inner_text().strip()) < 20:
            raise RuntimeError("棚小智回复未显示在对话区域。")

    scene(6, ask_question)

    def create_task() -> None:
        nonlocal created_title
        field = page.get_by_placeholder("问棚小智一个问题，Enter发送，Shift+Enter换行")
        field.fill(TASK_PROMPT)
        with page.expect_response(lambda r: r.url.endswith("/api/guest/ai/chat"), timeout=90_000) as response:
            page.get_by_role("button", name="发送").click()
        result = response.value
        data = result.json()
        actions = data.get("actions") or []
        if result.status != 200 or not actions:
            raise RuntimeError(f"棚小智未生成任务动作，HTTP {result.status}。不输出伪造的成功视频。")
        action = actions[0]
        created_title = action.get("title", "")
        if action.get("greenhouse_id") != 101 or action.get("priority") != "high" or not created_title:
            raise RuntimeError("模型返回的目标大棚或优先级不符合演示要求。")
        page.get_by_text("已在当前浏览器创建：", exact=False).wait_for(timeout=20_000)

    scene(7, create_task)

    def verify_task() -> None:
        page.locator(".ai-global-drawer .ant-drawer-close").evaluate("button => button.click()")
        page.locator(".ai-global-drawer").wait_for(state="hidden", timeout=15_000)
        page.get_by_role("button", name="任务中心").click()
        task_row = page.locator(".v17-task-table .v17-task-title").filter(has_text=created_title)
        task_row.wait_for(timeout=20_000)
        task_row.click()
        page.get_by_text("待提交", exact=True).first.wait_for(timeout=15_000)
        page.mouse.move(870, 450)

    scene(8, verify_task)

    def verify_ephemeral() -> None:
        url = re.sub(r"[?&]task_id=\d+", "", page.url).rstrip("?")
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        page.get_by_role("button", name="任务中心").click()
        page.get_by_text("巡检滴灌管路", exact=True).first.wait_for(timeout=20_000)
        if page.get_by_text(created_title, exact=True).count():
            raise RuntimeError("刷新后游客新任务仍存在，与不存档预期不符。")

    scene(9, verify_ephemeral)

    def closing() -> None:
        page.mouse.move(1270, 740)

    scene(10, closing)
    return scene_starts, time.monotonic() - started


def encode_mp4(webm: Path, audio: Path | None, output: Path) -> None:
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [ffmpeg, "-y", "-i", str(webm)]
    if audio:
        command += ["-i", str(audio)]
    command += [
        "-map", "0:v:0", "-c:v", "libx264", "-preset", "veryfast",
        "-vf", "scale=1920:1080:flags=lanczos,fps=30,format=yuv420p",
        "-b:v", "3500k", "-maxrate", "4000k", "-bufsize", "7000k",
    ]
    if audio:
        command += ["-map", "1:a:0", "-c:a", "aac", "-b:a", "128k", "-shortest"]
    else:
        command += ["-an"]
    command += ["-movflags", "+faststart", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
    if result.returncode:
        raise RuntimeError(f"MP4 编码失败：{result.stderr[-1500:]}")
    if output.stat().st_size > 200_000_000:
        raise RuntimeError("录制完成，但 MP4 超过 200 MB，请降低码率后重新编码。")


def verify_mp4(output: Path, expect_audio: bool) -> float:
    import imageio_ffmpeg

    result = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(output)],
        capture_output=True, text=True, timeout=20, check=False,
    )
    metadata = result.stderr
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", metadata)
    if not match or "Video: h264" not in metadata or (expect_audio and "Audio: aac" not in metadata):
        raise RuntimeError("MP4 音视频流校验失败。")
    duration = int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])
    if duration > 300:
        raise RuntimeError(f"MP4 实际时长 {duration:.1f} 秒，超过 5 分钟限制。")
    return duration


def main() -> int:
    parser = argparse.ArgumentParser(description="自动录制本地游客模式演示视频")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="输出 MP4 路径")
    parser.add_argument("--headless", action="store_true", help="浏览器不显示；默认可见并自动操作")
    parser.add_argument("--no-voice", action="store_true", help="不生成中文旁白")
    parser.add_argument("--dry-run", action="store_true", help="仅检查自动操作，不输出视频")
    parser.add_argument("--quick", action="store_true", help="缩短镜头停留时间，仅用于彩排")
    args = parser.parse_args()
    ensure_services()
    if not EDGE.is_file():
        raise RuntimeError(f"未找到 Microsoft Edge：{EDGE}")

    with tempfile.TemporaryDirectory(prefix="pengzhi-record-") as temp_name:
        temp = Path(temp_name)
        voice_files: list[Path] = []
        voice_durations: list[float] = []
        if not args.no_voice and not args.dry_run:
            print("正在生成中文旁白……", flush=True)
            for i, current in enumerate(SCENES):
                output = temp / f"voice-{i:02d}.wav"
                voice_durations.append(synthesize_voice(current.narration, output))
                voice_files.append(output)
            print(f"计划镜头 {sum(scene.seconds for scene in SCENES):.0f} 秒；最长旁白 {max(voice_durations):.1f} 秒。")
        else:
            voice_durations = [0.0] * len(SCENES)

        video = None
        raw: Path | None = None
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=str(EDGE), headless=args.headless,
                args=["--no-first-run", "--disable-notifications"],
            )
            context = browser.new_context(
                viewport={"width": 1440, "height": 810},
                device_scale_factor=1,
                record_video_dir=str(temp / "raw") if not args.dry_run else None,
                record_video_size={"width": 1440, "height": 810} if not args.dry_run else None,
            )
            context.route(
                "**/*",
                lambda route: route.abort()
                if urlparse(route.request.url).scheme in {"http", "https"}
                and urlparse(route.request.url).hostname not in {"127.0.0.1", "localhost"}
                else route.continue_(),
            )
            page = context.new_page()
            video = page.video
            page.set_default_timeout(20_000)
            try:
                scene_starts, duration = run_workflow(
                    page, args.quick, voice_durations, not args.no_voice and not args.dry_run
                )
            except Exception:
                failed = ROOT / "演示视频" / "录制失败现场.png"
                failed.parent.mkdir(exist_ok=True)
                page.screenshot(path=str(failed), full_page=False)
                print(f"录制中断，现场截图：{failed}", file=sys.stderr)
                raise
            finally:
                context.close()
                if video is not None:
                    raw = Path(video.path())
                browser.close()

        if args.dry_run:
            print(f"自动操作彩排通过，用时 {duration:.1f} 秒。")
            return 0
        if duration > 299:
            raise RuntimeError(f"镜头录制用时 {duration:.1f} 秒，超过 5 分钟限制；未生成提交版 MP4。")
        if raw is None:
            raise RuntimeError("浏览器未生成录屏文件。")
        audio = None
        if voice_files:
            audio = temp / "narration.wav"
            build_narration(scene_starts, voice_files, audio, duration)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        encode_mp4(raw, audio, args.output)
        actual_duration = verify_mp4(args.output, bool(audio))
        print(f"录制完成：{args.output}")
        print(f"实际时长 {actual_duration:.1f} 秒；文件大小 {args.output.stat().st_size / 1_000_000:.1f} MB。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
