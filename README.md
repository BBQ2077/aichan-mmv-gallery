# aichan-mmv-gallery

AI 娘（DeepSeek 鯨魚娘、Claude 娘、GPT 白龍娘、Gemini 娘、Grok 娘等）角色圖庫，以及兩支 MMV 的製作素材與腳本：

- **《潮與牆》**：AI 娘中世紀戰爭 MMV（開源聯盟 vs 閉源帝國）
- **《浪尖》**：2026 股市年度總結 MMV，DeepSeek 鯨魚娘串場

## 資料夾

| 資料夾 | 內容 | 張數 |
|---|---|---|
| `characters/ai-chan-sheets/` | 10 位 AI 娘設定圖：三視圖、表情、服裝、道具（每位 22 張） | 220 |
| `characters/deepseek-pose-gallery/` | DeepSeek 鯨魚娘姿勢圖（above／below 兩組） | 80 |
| `characters/deepseek-cutouts/` | 鯨魚娘去背貼紙圖（透明底 PNG） | 94 |
| `wave-2026/scenes/` | 《浪尖》場景圖：交易桌、海底、浪頭、天空、黃金、比特幣等 | 37 |
| `tide-and-wall/backgrounds/scenes/` | 《潮與牆》場景背景（1920×1088） | 107 |
| `tide-and-wall/backgrounds/alt-angles/` | 同場景的替代機位 | 80 |
| `tide-and-wall/backgrounds/panorama/` | 大場面全景 | 12 |
| `tide-and-wall/backgrounds/muse/` | 補充場景 | 13 |
| `tide-and-wall/backgrounds/burst-states/` | 爆裂、崩塌狀態 | 8 |
| `tide-and-wall/props-closeups/` | 道具與特寫：地圖、鐵閘、巨弩、旗幟、書頁、鑰匙等 | 27 |
| `tide-and-wall/armies/` | 各陣營軍隊 | 50 |
| `tide-and-wall/characters/poses/` | 角色姿勢、關鍵張 | 147 |
| `tide-and-wall/characters/variants/` | 姿勢微變體 | 45 |
| `tide-and-wall/characters/inbetweens/` | 補間張 | 20 |
| `tide-and-wall/characters/rig-layers/` | 武器、部位分層（做局部動作用） | 41 |
| `tide-and-wall/characters/sd-layers/` | 部位分層測試 | 20 |
| `tide-and-wall/cutouts/` | 角色去背圖 | 95 |
| `tide-and-wall/fx/` | 特效素材：箭雨、燃燒書頁、碎石等 | 28 |
| `tools/` | 製作腳本（見下） | 42 |

## 腳本（`tools/`）

Python（PIL、numpy）＋ ffmpeg，Windows 環境寫成，路徑需依自己的環境修改。

**`tools/wave-2026/`（《浪尖》）**

| 檔案 | 用途 |
|---|---|
| `eng.py` | 逐格合成引擎：鏡頭、裁切推拉、角色貼紙外框、K 棒、走勢圖、計數器、卡拉 OK 字幕、閃白／震動／色差等後製事件 |
| `eng_long.py` | 數十年月線長圖，從 2026 拉遠到全歷史 |
| `eng_run.py` | 行情奔跑：線頭跟拍、玻璃碎字、閃電、碎片 |
| `eng_sea.py` | 海面線圖：水面、水下光紋、氣泡、浪花 |
| `eng_vt.py` | VTuber 版行情：大 K 棒從開盤長到收盤、長 K 特效、角色固定側邊並隨事件換動作與外框色圈 |
| `cutout2.py` | 白底圖去背，輸出乾淨的透明 PNG |
| `muse.py`、`muse_jobs.py` | fal Meta Muse 批次生圖與提示詞（金鑰讀環境變數 `FAL_KEY`） |
| `par_render.py`、`clip.py` | 多程序平行渲染整片／片段，接上混音 |
| `still1.py`、`stills.py` | 抽單格預覽 |
| `sfx_mix.py`、`sfx_meas.py` | 小中大三層音效混音（輪替、隨機音高、ducking）、量測素材頻段與響度 |
| `beats.py`、`song_info.py` | 節拍與段落分析 |
| `mkreq.py`、`yue.py`、`song_batch.sh` | YuE 歌曲生成請求與批次 |
| `up_muse.py` | RealESRGAN 放大 |
| `sheet_rgba.py` | 透明圖總覽表 |

**`tools/tide-and-wall/`（《潮與牆》）**

| 檔案 | 用途 |
|---|---|
| `render2.py`、`par_render2.sh` | 剪輯表渲染器與平行渲染 |
| `sfx3.py` | 分層音效混音 |
| `upscale.py` | 放大 |
| `parts_split.py`、`weapon_layer.py` | 部位、武器分層拆圖 |
| `jitter.py`、`shake.py`、`ecu_check.py` | 鏡頭抖動量測、震動、大特寫檢查 |
| `sheet2.py`、`contact.py`、`fsheet.py`、`shotinfo.py` | 縮圖表、鏡頭資訊 |
| `seedream.py`、`sd.py`、`prompt_lib.py` | fal Seedream／本機模型生圖與提示詞庫（金鑰讀環境變數 `FAL_KEY`） |
| `dl_aichan.py` | 下載 AI 娘設定圖 |
| `beats.py`、`abc_sections.py`、`audio_scan.py`、`yue.py` | 節拍、ABC 譜段落、音訊分析、YuE 生成 |

## 來源與授權

- `characters/ai-chan-sheets/`：來自 [lmy414/ai-chan-sheets](https://github.com/lmy414/ai-chan-sheets)，基於 ZipZipPipe（胖次狐）的 AI 娘立繪，授權 **CC BY-NC-SA 4.0**（非商業）。
- 其餘角色圖、場景圖、去背圖與特效圖以上述角色設定為基礎，用 AI 生成或後製而成，一併以 **[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)** 釋出：可轉載、改作，需標示來源、非商業使用、以相同授權分享。
- `tools/` 內的程式碼以 MIT 授權釋出。
