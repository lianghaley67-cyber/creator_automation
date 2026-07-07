"""
AI Coding Assistant - 文件操作和 AI 对话 API
支持：文件读写、AI 对话（文本+图片）、流式响应
"""
import os
import base64
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/ai-coding", tags=["AI Coding"])

# 项目根目录（限制文件访问范围）
PROJECT_ROOT = Path(__file__).parent.parent


def _anthropic_client():
    """Create the Anthropic client only when the AI coding chat endpoint is used."""
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError("Anthropic SDK 未安装，请先安装依赖：pip install anthropic") from exc
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 未配置，无法使用 AI Coding 对话。")
    return anthropic.Anthropic(api_key=api_key)


# ============ 数据模型 ============
class ChatMessage(BaseModel):
    """对话消息"""
    role: str  # "user" 或 "assistant"
    content: str
    images: Optional[List[str]] = None  # base64 编码的图片


class ChatRequest(BaseModel):
    """对话请求"""
    messages: List[ChatMessage]
    model: str = "claude-sonnet-5"
    max_tokens: int = 4096


class FileInfo(BaseModel):
    """文件信息"""
    name: str
    path: str
    is_directory: bool
    size: Optional[int] = None


class FileOperation(BaseModel):
    """文件操作请求"""
    path: str
    content: Optional[str] = None  # 写入文件时使用


# ============ 文件操作 API ============
@router.get("/files", response_model=List[FileInfo])
async def list_files(path: str = ""):
    """列出目录下的文件"""
    target_path = PROJECT_ROOT / path if path else PROJECT_ROOT

    if not target_path.exists():
        raise HTTPException(status_code=404, detail="路径不存在")

    if not target_path.is_dir():
        raise HTTPException(status_code=400, detail="不是目录")

    files = []
    try:
        for item in sorted(target_path.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
            # 跳过隐藏文件和目录
            if item.name.startswith('.') or item.name == '__pycache__':
                continue

            files.append(FileInfo(
                name=item.name,
                path=str(item.relative_to(PROJECT_ROOT)),
                is_directory=item.is_dir(),
                size=item.stat().st_size if item.is_file() else None
            ))
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权限访问")

    return files


@router.get("/files/content")
async def get_file_content(path: str):
    """读取文件内容"""
    target_path = PROJECT_ROOT / path

    if not target_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    if not target_path.is_file():
        raise HTTPException(status_code=400, detail="不是文件")

    # 检查文件大小（限制 1MB）
    if target_path.stat().st_size > 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件过大")

    try:
        content = target_path.read_text(encoding='utf-8')
        return {"content": content}
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="无法读取文件（可能是二进制文件）")


@router.post("/files/content")
async def save_file_content(request: FileOperation):
    """保存文件内容"""
    if not request.content:
        raise HTTPException(status_code=400, detail="内容不能为空")

    target_path = PROJECT_ROOT / request.path

    # 确保父目录存在
    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        target_path.write_text(request.content, encoding='utf-8')
        return {"success": True, "message": "保存成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


# ============ AI 对话 API ============
@router.post("/chat")
async def chat_with_ai(request: ChatRequest):
    """与 AI 对话（支持图片，流式响应）"""

    async def generate():
        try:
            # 构建消息列表
            messages = []
            for msg in request.messages:
                if msg.images:
                    # 有图片：多模态消息
                    content = [{"type": "text", "text": msg.content}]
                    for img in msg.images:
                        # img 是 base64 字符串（去掉 data:image/xxx;base64, 前缀）
                        if ',' in img:
                            img = img.split(',')[1]
                        content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img
                            }
                        })
                    messages.append({"role": msg.role, "content": content})
                else:
                    # 纯文本消息
                    messages.append({"role": msg.role, "content": msg.content})

            # 调用 Anthropic API（流式）
            client = _anthropic_client()
            with client.messages.stream(
                model=request.model,
                max_tokens=request.max_tokens,
                messages=messages
            ) as stream:
                for text in stream.text_stream:
                    # SSE 格式
                    yield f"data: {text}\n\n"

        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """上传图片（返回 base64）"""
    # 检查文件类型
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="只能上传图片")

    # 读取文件内容
    content = await file.read()

    # 检查文件大小（限制 5MB）
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片过大（限制 5MB）")

    # 转换为 base64
    base64_data = base64.b64encode(content).decode('utf-8')
    data_url = f"data:{file.content_type};base64,{base64_data}"

    return {"base64": data_url}
