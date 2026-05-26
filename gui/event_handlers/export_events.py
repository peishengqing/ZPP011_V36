# -*- coding: utf-8 -*-
"""瀵煎嚭銆丳PT鐢熸垚銆佸浠界瓑浜嬩欢"""

import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import pandas as pd
from ppt_generator import run_ppt_generation as _run_ppt
from widgets import C
from core.exporter import ExcelExporter
import threading, datetime
from openpyxl import Workbook, load_workbook


class ExportEvents:
    """瀵煎嚭銆丳PT鐢熸垚銆佸浠界瓑浜嬩欢"""

    def generate_ppt(self):
        """閫夋嫨 Excel 鍒嗘瀽缁撴灉锛岀敓鎴?PPT 鎶ュ憡"""

        excel_path = filedialog.askopenfilename(
            title="閫夋嫨 zpp011 鍋忓樊鍒嗘瀽 Excel 鏂囦欢",
            filetypes=[("Excel 鏂囦欢", "*.xlsx *.xls"), ("鎵€鏈夋枃浠?, "*.*")],
        )

        if not excel_path:
            return

        out_dir = self.output_dir.get() or os.path.dirname(excel_path)

        base = os.path.splitext(os.path.basename(excel_path))[0]

        if self.audit_data is None or self.audit_data.empty:
            messagebox.showwarning("鎻愮ず", "璇峰厛鍔犺浇骞跺垎鏋愭暟鎹悗鍐嶇敓鎴?PPT锛?)

            return

        import datetime

        default_name = (
            self.config.get(
                "export.default_ppt_filename", "ZPP011鍋忓樊鍒嗘瀽_{datetime}.pptx"
            ).format(datetime=datetime.datetime.now().strftime("%Y%m%d_%H%M"))
            + ".pptx"
        )

        ppt_output = filedialog.asksaveasfilename(
            initialdir=out_dir,
            initialfile=default_name,
            defaultextension=".pptx",
            filetypes=[("PPT 鏂囦欢", "*.pptx"), ("鎵€鏈夋枃浠?, "*")],
            title="淇濆瓨 PPT 鎶ュ憡",
        )

        if not ppt_output:
            return

        self.log("馃搳 寮€濮嬬敓鎴?PPT...", "info")

        self.ppt_btn.configure(state="disabled", text="鐢熸垚涓?..")

        self.status_lbl.configure(text="姝ｅ湪鐢熸垚 PPT...", fg=C["purple"])

        def worker():

            try:

                def progress(pct):

                    self.root.after(0, lambda p=pct: self._update_ppt_progress(p))

                self.audit_presenter.generate_ppt(
                    output_path=ppt_output, progress_callback=progress
                )

                self.root.after(0, lambda: self._on_ppt_done(ppt_output))

            except Exception as e:
                self.root.after(0, lambda e=e: self._on_ppt_error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _update_ppt_progress(self, pct):
        """鏇存柊 PPT 鐢熸垚杩涘害鏄剧ず"""
        self.status_lbl.configure(text=f"姝ｅ湪鐢熸垚 PPT... {int(pct)}%", fg=C["purple"])

    def _on_ppt_done(self, output_path):

        self.ppt_btn.configure(state="normal", text="馃搳 鐢熸垚PPT")

        self.status_lbl.configure(
            text=f"PPT 宸茬敓鎴?鈥?{os.path.basename(output_path)}", fg=C["green"]
        )

        self.log(f"鉁?PPT 宸蹭繚瀛橈細{output_path}", "success")

        try:
            os.startfile(output_path)

        except Exception:
            pass

    def _on_ppt_error(self, msg):

        self.ppt_btn.configure(state="normal", text="馃搳 鐢熸垚PPT")

        self.status_lbl.configure(text="PPT 鐢熸垚鍑洪敊", fg=C["danger"])

        self.log(f"鉂?PPT 鐢熸垚澶辫触锛歿msg}", "error")

        messagebox.showerror("PPT 鐢熸垚鍑洪敊", msg)

    def generate_excel_direct(self):
        """寮瑰嚭鍙﹀瓨涓哄璇濇锛岀敓鎴?Excel 鍒嗘瀽琛ㄦ牸"""

        input_path = self.input_file.get()

        if not input_path or not os.path.exists(input_path):
            messagebox.showerror("閿欒", "璇峰厛閫夋嫨杈撳叆鏂囦欢锛?)

            return

        # 鈹€鈹€ 灏濊瘯浠庡師濮嬫暟鎹腑鑾峰彇鏃ユ湡鑼冨洿锛岀敤浜庨粯璁ゆ枃浠跺悕 鈹€鈹€

        date_tag = ""

        try:
            df_raw = pd.read_excel(input_path, sheet_name="Data")

            # 鏌ユ壘鍙兘鐨勬棩鏈熷垪

            date_col = None

            for col in ["璁㈠崟寮€濮嬫棩鏈?, "璁㈠崟鏃ユ湡", "鏃ユ湡"]:
                if col in df_raw.columns:
                    date_col = col

                    break

            if date_col is not None:
                dates = pd.to_datetime(df_raw[date_col], errors="coerce").dropna()

                if not dates.empty:
                    d_min = dates.min().strftime("%Y%m%d")

                    d_max = dates.max().strftime("%m%d")

                    date_tag = f"{d_min}-{d_max}"

        except Exception:
            pass

        # 濡傛灉浠庢暟鎹腑鑾峰彇澶辫触锛屽洖閫€鍒版墜鍔ㄨ緭鍏ユ垨褰撳墠鏈堜唤

        if not date_tag:
            start_str = self.start_date.get().strip()

            end_str = self.end_date.get().strip()

            if start_str and end_str:
                date_tag = (
                    f"{start_str.replace('-', '')[:8]}-{end_str.replace('-', '')[-4:]}"
                )

            else:
                now = datetime.now()

                first_day = now.replace(day=1).strftime("%Y%m%d")

                # 浣跨敤 calendar 璁＄畻鏈堟湯

                import calendar

                last_day_num = calendar.monthrange(now.year, now.month)[1]

                last_day = now.replace(day=last_day_num).strftime("%Y%m%d")

                date_tag = f"{first_day}-{last_day[-4:]}"

        # 鈹€鈹€ 鏋勫缓榛樿璺緞鍜屾枃浠跺悕 鈹€鈹€

        default_dir = os.path.join(os.path.expanduser("~"), "ZPP011鍋忓樊鍒嗘瀽")

        os.makedirs(default_dir, exist_ok=True)

        default_name = f"ZPP011鍋忓樊鍒嗘瀽_{date_tag}.xlsx"

        # 鈹€鈹€ 寮瑰嚭鍙﹀瓨涓哄璇濇 鈹€鈹€

        file_path = filedialog.asksaveasfilename(
            initialdir=default_dir,
            initialfile=default_name,
            defaultextension=".xlsx",
            filetypes=[("Excel 鏂囦欢", "*.xlsx"), ("鎵€鏈夋枃浠?, "*.*")],
            title="淇濆瓨鍋忓樊鍒嗘瀽琛ㄦ牸",
        )

        if not file_path:
            return  # 鐢ㄦ埛鍙栨秷

        self.excel_btn.configure(state="disabled", text="鐢熸垚涓?..")

        self.status_lbl.configure(text="姝ｅ湪鐢熸垚琛ㄦ牸...", fg=C["purple"])

        self.log("馃搵 寮€濮嬬敓鎴愬亸宸垎鏋愯〃鏍?..", "info")

        threading.Thread(
            target=self._generate_excel_thread, args=(file_path,), daemon=True
        ).start()

    def _generate_excel_thread(self, output_path: str):
        """鍚庡彴绾跨▼锛氬鎵?AuditPresenter 鐢熸垚鍋忓樊鍒嗘瀽 Excel锛屽甫璇︾粏閿欒鏃ュ織"""

        import traceback

        try:
            result = self.audit_presenter.generate_excel_direct(
                input_file=self.input_file.get(),
                output_path=output_path,
                alt_pairs=self.alt_pairs,
                start_date=self.start_date.get() or None,
                end_date=self.end_date.get() or None,
                material_search=self.material_search.get() or None,
                log_cb=self.log,
            )

            def on_success():

                self.log(f"\u2705 琛ㄦ牸鐢熸垚锛歿os.path.basename(result)}", "success")

                self.excel_btn.configure(state="normal", text="\U0001f4cb 鐢熸垚琛ㄦ牸")

                self.status_lbl.configure(
                    text=f"宸茬敓鎴愶細{os.path.basename(result)}", fg=C["green"]
                )

                _name = os.path.basename(result)

                _msg = "琛ㄦ牸宸茬敓鎴愶細" + _name + chr(10) + chr(10) + "鏄惁绔嬪嵆鎵撳紑锛?

                if messagebox.askyesno("鐢熸垚鎴愬姛", _msg):
                    try:
                        os.startfile(result)

                        self.log(f"\u2705 宸叉墦寮€鏂囦欢锛歿result}", "info")

                    except Exception as oe:
                        self.log(f"\u26a0\ufe0f 鏃犳硶鎵撳紑鏂囦欢锛歿oe}", "warning")

                        messagebox.showwarning("鎵撳紑澶辫触", f"鏃犳硶鎵撳紑鏂囦欢锛歿oe}")

            self.root.after(0, on_success)

        except Exception as e:
            tb = traceback.format_exc()

            error_msg = str(e)

            if "Permission denied" in error_msg or "PermissionError" in error_msg:
                _warn_msg = (
                    "\u26a0\ufe0f 鏃犳硶淇濆瓨鏂囦欢"
                    + chr(10)
                    + chr(10)
                    + "\u53ef\u80fd\u7684\u539f\u56e0\uff1a"
                    + chr(10)
                    + "  鈥?鏂囦欢宸茬敤 Excel 鎵撳紑"
                    + chr(10)
                    + "  鈥?鏂囦欢琚?WPS 鎴栧叾浠栫▼搴忓崰鐢?
                    + chr(10)
                    + chr(10)
                    + "瑙ｅ喅鏂规硶锛?
                    + chr(10)
                    + "  1. 鍏抽棴 Excel 涓墦寮€鐨勮繖涓枃浠?
                    + chr(10)
                    + "  2. 鐐瑰嚮銆岀敓鎴愯〃鏍笺€嶉噸璇?
                    + chr(10)
                    + "  3. 鎴栬€呭彟瀛樹负鍏朵粬鏂囦欢鍚?
                )

                self.root.after(
                    0, lambda: messagebox.showwarning("鏂囦欢琚崰鐢?, _warn_msg)
                )

                self.root.after(
                    0,
                    lambda: self.log(
                        "\u26a0\ufe0f 鏂囦欢琚崰鐢紝璇峰叧闂?Excel 鍚庨噸璇?, "warning"
                    ),
                )

            else:
                _err = str(e)

                self.root.after(
                    0,
                    lambda: messagebox.showerror("鐢熸垚澶辫触", f"鐢熸垚琛ㄦ牸鏃跺嚭閿欙細{_err}"),
                )

                self.root.after(
                    0, lambda: self.log(f"\u274c 琛ㄦ牸鐢熸垚澶辫触锛歿_err}", "error")
                )

            self.root.after(0, lambda: self.log(tb, "error"))

            self.root.after(
                0,
                lambda: self.excel_btn.configure(
                    state="normal", text="\U0001f4cb 鐢熸垚琛ㄦ牸"
                ),
            )

    # 鈹€鈹€ 鏍戝舰瑙嗗浘锛坴31 鏂板锛夆攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _export_audit_excel(self, cancel_flag=None, progress_callback=None):
        """Async export audit result (launcher)"""

        if self.audit_data is None or len(self.audit_data) == 0:
            messagebox.showwarning("Tip", "No data to export")

            return

        out_path = (
            self.output_dir.get()
            or os.path.dirname(self.input_file.get())
            or os.getcwd()
        )

        file_path = filedialog.asksaveasfilename(
            initialdir=out_path,
            initialfile="ZPP011_Audit_Result.xlsx",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
        )

        if not file_path:
            return

        # Start async task

        self.is_exporting = True

        self.task_manager.run(
            lambda c, p: ExcelExporter.export(
                self.audit_data.copy(), file_path, cancel_flag=c, progress_callback=p
            ),
            task_id="export_audit_excel",
            on_progress=self._on_export_progress,
            on_done=self._on_export_done,
            on_error=self._on_export_error,
        )

    def _on_export_progress(self, current, total, **kwargs):
        """Export progress callback"""

        if hasattr(self, "progress_bar") and self.progress_bar:
            self.progress_bar["value"] = current

            self.progress_bar["maximum"] = total

            percent = int(current / total * 100) if total > 0 else 0

            eta_seconds = kwargs.get("eta_seconds", 0)

            eta_str = f"ETA {int(eta_seconds)}s" if eta_seconds > 0 else ""

            self.progress_bar.configure(
                text=f"Exporting {current}/{total} ({percent}%) {eta_str}"
            )

            self.root.update_idletasks()

    def _on_export_done(self, result):
        """Export success callback"""

        self.is_exporting = False

        if hasattr(self, "progress_bar") and self.progress_bar:
            self.progress_bar.stop()

            self.progress_bar.pack_forget()

        file_path = result.get("file_path", "")

        if file_path and os.path.exists(file_path):
            if messagebox.askyesno(
                "Success", f"Exported to:\n{file_path}\n\nOpen folder?"
            ):
                os.startfile(os.path.dirname(file_path))

            self.log(f"Audit result exported (async): {file_path}", "success")

        else:
            messagebox.showinfo("Success", "Export completed!")

    def _on_export_error(self, error):
        """Export error callback"""

        self.is_exporting = False

        if hasattr(self, "progress_bar") and self.progress_bar:
            self.progress_bar.stop()

            self.progress_bar.pack_forget()

        # Clean temp files

        temp_dir = os.path.join(os.path.dirname(__file__), "..", "temp")

        if os.path.exists(temp_dir):
            for f in os.listdir(temp_dir):
                if f.endswith(".tmp.xlsx"):
                    try:
                        os.remove(os.path.join(temp_dir, f))

                    except:
                        pass

        messagebox.showerror("Error", f"Export failed: {error}")

        self.log(f"Export failed: {error}", "error")

    def _export_audit_backup(self):

        default_name = f"瀹℃牳璁板綍澶囦唤_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

        file_path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP 鍘嬬缉鏂囦欢", "*.zip")],
            initialfile=default_name,
            title="瀵煎嚭瀹℃牳璁板綍澶囦唤",
        )

        if not file_path:
            return

        try:
            storage.export_audit_backup(file_path, log_cb=self.log)

            self.log(f"鉁?瀹℃牳璁板綍宸插鍑猴細{file_path}", "success")

            messagebox.showinfo("瀵煎嚭鎴愬姛", f"澶囦唤鏂囦欢宸蹭繚瀛樺埌锛歕n{file_path}")

        except FileNotFoundError:
            self.log("鉂?瀵煎嚭澶辫触锛氬鏍告暟鎹簱涓嶅瓨鍦?, "error")

            messagebox.showerror(
                "瀵煎嚭澶辫触", "瀹℃牳鏁版嵁搴撲笉瀛樺湪锛岃鍏堜繚瀛樺鏍歌褰曞悗鍐嶅鍑恒€?
            )

        except Exception as e:
            self.log(f"鉂?瀵煎嚭澶辫触锛歿e}", "error")

            messagebox.showerror("瀵煎嚭澶辫触", str(e))

    def _import_audit_backup(self):

        file_path = filedialog.askopenfilename(
            title="閫夋嫨瀹℃牳璁板綍澶囦唤鏂囦欢",
            filetypes=[("ZIP 鍘嬬缉鏂囦欢", "*.zip"), ("鎵€鏈夋枃浠?, "*.*")],
        )

        if not file_path:
            return

        try:
            storage.import_audit_backup(file_path, log_cb=self.log)

            self.log("鉁?瀹℃牳璁板綍宸蹭粠澶囦唤鎭㈠锛屼笅娆″姞杞芥椂鐢熸晥", "success")

            messagebox.showinfo(
                "瀵煎叆鎴愬姛", "瀹℃牳璁板綍宸叉仮澶嶃€俓n閲嶆柊鍔犺浇鏁版嵁鏃跺皢鑷姩鍖归厤鍘嗗彶瀹℃牳銆?
            )

        except Exception as e:
            self.log(f"鉂?瀵煎叆澶辫触锛歿e}", "error")

            messagebox.showerror("瀵煎叆澶辫触", str(e))

    # 鈹€鈹€ 鐗堟湰鏃ュ織宸茶縼绉诲埌 utils/version_history.py 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    # 鍘?_CHANGELOG_EMBEDDED 纭紪鐮佸凡鍒犻櫎锛岄€氳繃瀵煎叆鍔ㄦ€佽鍙?

    _CHANGELOG_EMBEDDED = None  # 鍗犱綅锛屼繚鎸佸悜鍚庡吋瀹?

    # 鈹€鈹€ 鍏叡鍑芥暟锛氳幏鍙?changelog.json 璺緞 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def _export_log(self):
        """瀵煎嚭鏃ュ織鍒版枃浠?""

        try:
            import datetime as _dt

            ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")

            default_name = self.config.get(
                "export.default_log_filename", "ZPP011鏃ュ織_{ts}.txt"
            ).format(ts=ts)

            path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("鏂囨湰鏂囦欢", "*.txt"), ("鎵€鏈夋枃浠?, "*.*")],
                initialfile=default_name,
                title="瀵煎嚭鏃ュ織",
            )

            if not path:
                return

            with open(path, "w", encoding="utf-8") as f:
                f.write(self.log_text.get("1.0", "end"))

            self.log(f"鏃ュ織宸插鍑猴細{os.path.basename(path)}", "success")

        except Exception as e:
            messagebox.showerror("瀵煎嚭澶辫触", str(e))

    def _export_changelog(self):
        """瀵煎嚭鐗堟湰鏃ュ織"""

        try:
            # 浣跨敤鍏叡鍑芥暟鑾峰彇 changelog.json 璺緞

            cl_path = self._get_changelog_path() or ""

            # 璇诲彇 changelog.json

            cl_data = {}

            if os.path.isfile(cl_path):
                with open(cl_path, "r", encoding="utf-8") as f:
                    cl_data = json.load(f)

            # 鏍煎紡鍖栨棩蹇?

            lines = []

            app_name = cl_data.get("app_name", "浜戝崡杈惧埄ZPP011鐢熶骇鍋忓樊鍒嗘瀽鍣?)

            author = cl_data.get("author", "瑁寸洓娓?)

            versions = cl_data.get("versions", [])

            lines.append(app_name)

            lines.append(f"浣滆€咃細{author}")

            lines.append("=" * 50)

            for v in versions:
                lines.append(f"\n銆恵v.get('version', '')}銆憑v.get('date', '')}")

                for feat in v.get("features", []):
                    lines.append(f"  鉁?{feat}")

                for fix in v.get("fixes", []):
                    lines.append(f"  馃敡 {fix}")

                for opt in v.get("optimizations", []):
                    lines.append(f"  鈿?{opt}")

                for les in v.get("lessons", []):
                    lines.append(f"  馃搶 {les}")

            changelog_text = "\n".join(lines)

            # 寮瑰嚭淇濆瓨瀵硅瘽妗?

            import datetime as _dt

            ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")

            default_name = self.config.get(
                "export.default_changelog_filename", "ZPP011鐗堟湰鏃ュ織_{ts}.txt"
            ).format(ts=ts)

            path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("鏂囨湰鏂囦欢", "*.txt"), ("鎵€鏈夋枃浠?, "*.*")],
                initialfile=default_name,
                title="瀵煎嚭鐗堟湰鏃ュ織",
            )

            if not path:
                return

            with open(path, "w", encoding="utf-8") as f:
                f.write(changelog_text)

            self.log(f"鐗堟湰鏃ュ織宸插鍑猴細{os.path.basename(path)}", "success")

            messagebox.showinfo("瀵煎嚭鎴愬姛", f"鐗堟湰鏃ュ織宸蹭繚瀛樺埌锛歕n{path}")

        except Exception as e:
            self.log(f"瀵煎嚭鐗堟湰鏃ュ織澶辫触锛歿e}", "error")

            messagebox.showerror("瀵煎嚭澶辫触", str(e))

    def _save_audit_back(self):
        """淇濆瓨瀹℃牳缁撴灉鍒板師 Excel锛屽悓鏃跺悓姝ュ埌鏈湴鏁版嵁搴?""

        # 鈹€鈹€ 1. 鍓嶇疆妫€鏌?鈹€鈹€

        self.log("馃捑 姝ｅ湪淇濆瓨瀹℃牳缁撴灉...", "info")

        if self.audit_data is None or self.audit_data.empty:
            messagebox.showwarning("鎻愮ず", "娌℃湁瀹℃牳鏁版嵁鍙繚瀛?)

            return

        src_path = self.input_file.get()

        if not src_path or not os.path.exists(src_path):
            messagebox.showerror("閿欒", "鍘熷鏂囦欢涓嶅瓨鍦紝璇峰厛閫夋嫨姝ｇ‘鐨勮緭鍏ユ枃浠?)

            return

        try:
            # 鈹€鈹€ 2. 澶囦唤鍘熸枃浠?鈹€鈹€

            self.log("馃摝 姝ｅ湪澶囦唤鍘熸枃浠?..", "info")

            backup_dir = os.path.dirname(src_path)

            ts = datetime.now().strftime("%Y%m%d_%H%M%S")

            backup_name = f"{os.path.splitext(os.path.basename(src_path))[0]}_瀹℃牳鍓嶅浠絖{ts}.xlsx"

            backup_path = os.path.join(backup_dir, backup_name)

            shutil.copy2(src_path, backup_path)

            self.log(f"馃摝 宸插浠藉師鏂囦欢锛歿backup_name}", "info")

        except Exception as e:
            self.log(f"鈿?澶囦唤澶辫触锛歿e}", "warning")

            if not messagebox.askyesno(
                "澶囦唤澶辫触", f"鏃犳硶澶囦唤鍘熸枃浠讹細{e}\n鏄惁涓嶅浠界洿鎺ヤ繚瀛橈紵"
            ):
                return

        # 鈹€鈹€ 3. 鎵撳紑 Excel 鍐欏叆瀹℃牳缁撴灉 鈹€鈹€

        try:
            self.log("馃搨 姝ｅ湪鎵撳紑 Excel 鏂囦欢...", "info")

            wb = load_workbook(src_path)

            ws = wb["Data"]

            self.log(
                f"   Excel 宸叉墦寮€锛屽叡 {ws.max_row} 琛?x {ws.max_column} 鍒?, "info"
            )

        except Exception as e:
            self.log(f"鉂?鎵撳紑 Excel 澶辫触锛歿e}", "error")

            messagebox.showerror(
                "淇濆瓨澶辫触", f"鏃犳硶鎵撳紑鍘熷鏂囦欢锛歕n{e}\n璇峰叧闂?Excel 鍚庨噸璇曘€?
            )

            return

        # 鈹€鈹€ 4. 鏋勫缓寰呭啓鍏ョ殑鏁版嵁鍒楄〃 鈹€鈹€

        save_list = []

        # 璁㈠崟鍒楁煡鎵撅紙鏀寔澶氱鍒楀悕锛?

        order_col = None

        for possible in [
            "娴佺▼璁㈠崟",
            "璁㈠崟鍙?,
            "璁㈠崟缂栧彿",
            "璁㈠崟鍙风爜",
            "璁㈠崟No",
            "Order No",
            "鐢熶骇璁㈠崟",
        ]:
            if possible in self.audit_data.columns:
                order_col = possible

                break

        if order_col is None:
            wb.close()

            self.log(
                f"鉂?瀹℃牳鏁版嵁涓己灏戣鍗曞垪锛屽疄闄呭垪鍚? {list(self.audit_data.columns)[:10]}",
                "error",
            )

            messagebox.showerror(
                "淇濆瓨澶辫触",
                f"瀹℃牳鏁版嵁涓己灏戣鍗曞彿鍒楋紝鏃犳硶瀹氫綅鍘熻〃琛屻€俓n瀹為檯鍒楀悕: {list(self.audit_data.columns)[:10]}",
            )

            return

        for _, row in self.audit_data.iterrows():
            work_date = str(row.get("璁㈠崟鏃ユ湡", ""))[:10]

            order_no = str(row.get(order_col, ""))

            mat_code = str(row.get("缁勪欢鐗╂枡鍙?, ""))

            if not work_date or not order_no or not mat_code:
                continue

            # 鍙栨渶缁堝娉細浼樺厛鍙栧凡鏈夊娉紝鍏舵鍙?AI 寤鸿

            remark = str(row.get("澶囨敞鍘熷洜", "") or row.get("AI寤鸿", "") or "").strip()

            save_list.append((work_date, order_no, mat_code, remark))

        self.log(f"   寰呬繚瀛樿褰曪細{len(save_list)} 鏉?, "info")

        # 璋冭瘯锛氭墦鍗?save_list 鍓?鏉?

        if len(save_list) > 0:
            self.log(f"[DEBUG] save_list 鍓?鏉? {save_list[:3]}", "debug")

        # 鈹€鈹€ 5. 鍖归厤 Excel 琛ㄥご鍒楃储寮?鈹€鈹€

        headers = {}

        for col_idx in range(1, ws.max_column + 1):
            val = ws.cell(1, col_idx).value

            if val:
                headers[val.strip()] = col_idx

        date_col = headers.get("璁㈠崟寮€濮嬫棩鏈?) or headers.get("璁㈠崟鏃ユ湡")

        order_col_excel = headers.get("娴佺▼璁㈠崟") or headers.get("璁㈠崟鍙?)

        mat_col = headers.get("缁勪欢鐗╂枡鍙?) or headers.get("鐗╂枡缂栫爜")

        if not all([date_col, order_col_excel, mat_col]):
            wb.close()

            missing = []

            if not date_col:
                missing.append("鏃ユ湡")

            if not order_col_excel:
                missing.append("璁㈠崟鍙?)

            if not mat_col:
                missing.append("鐗╂枡缂栫爜")

            self.log(f"鉂?Excel 涓己灏戝叧閿垪锛歿', '.join(missing)}", "error")

            messagebox.showerror(
                "鍒楀尮閰嶅け璐?,
                f"鍘熷鏂囦欢涓湭鎵惧埌浠ヤ笅鍏抽敭鍒楋細\n{', '.join(missing)}\n鏃犳硶瀹氫綅鍐欏叆浣嶇疆銆?,
            )

            return

        self.log(
            f"   瀹氫綅鍒扮殑鍒楋細鏃ユ湡={date_col}, 璁㈠崟={order_col_excel}, 鐗╂枡={mat_col}",
            "info",
        )

        # 鈹€鈹€ 6. 鍐欏叆瀹℃牳鐘舵€佸垪 鈹€鈹€

        audit_cols = {
            "瀹℃牳鐘舵€?: None,
            "瀹℃牳澶囨敞": None,
            "瀹℃牳浜?: None,
            "瀹℃牳鏃堕棿": None,
        }

        next_col = ws.max_column + 1

        for col_name in audit_cols:
            if col_name in headers:
                audit_cols[col_name] = headers[col_name]

            else:
                ws.cell(1, next_col, col_name).font = Font(bold=True)

                audit_cols[col_name] = next_col

                next_col += 1

        self.log(
            f"   瀹℃牳鍒楋細瀹℃牳鐘舵€?{audit_cols['瀹℃牳鐘舵€?]}, 瀹℃牳澶囨敞={audit_cols['瀹℃牳澶囨敞']}",
            "info",
        )

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        auditor = os.getlogin()

        saved_count = 0

        match_count = 0

        for r_idx in range(2, ws.max_row + 1):
            r_date = (
                str(ws.cell(r_idx, date_col).value)[:10]
                if ws.cell(r_idx, date_col).value
                else ""
            )

            r_order = str(ws.cell(r_idx, order_col_excel).value).strip()

            r_mat = str(ws.cell(r_idx, mat_col).value).strip()

            match = next(
                (
                    item
                    for item in save_list
                    if item[0] == r_date and item[1] == r_order and item[2] == r_mat
                ),
                None,
            )

            if match:
                match_count += 1

                _, _, _, remark = match

                # 璋冭瘯锛氭墦鍗板尮閰嶅埌鐨勮鍙峰拰鍖归厤閿?

                self.log(
                    f"[DEBUG] 鍖归厤鍒拌 {r_idx}: date={r_date}, order={r_order}, mat={r_mat}, 鍐欏叆澶囨敞={remark[:20] if remark else '绌?}",
                    "debug",
                )

                ws.cell(r_idx, audit_cols["瀹℃牳鐘舵€?], "宸插娉? if remark else "鏈鏍?)

                ws.cell(r_idx, audit_cols["瀹℃牳澶囨敞"], remark)

                ws.cell(r_idx, audit_cols["瀹℃牳浜?], auditor)

                ws.cell(r_idx, audit_cols["瀹℃牳鏃堕棿"], now_str)

                saved_count += 1

        self.log(f"   鍖归厤鍒?{match_count} 琛岋紝寰呭啓鍏?{saved_count} 琛?, "info")

        # 鈹€鈹€ 7. 淇濆瓨 Excel 鏂囦欢 鈹€鈹€

        try:
            self.log("馃捑 姝ｅ湪淇濆瓨 Excel 鏂囦欢...", "info")

            wb.save(src_path)

            wb.close()

            self.log("   Excel 淇濆瓨鎴愬姛", "info")

        except PermissionError:
            wb.close()

            self.log("鉂?鏂囦欢琚崰鐢紝鏃犳硶淇濆瓨銆傝鍏抽棴 Excel 鍚庨噸璇曘€?, "error")

            messagebox.showerror(
                "淇濆瓨澶辫触", "鏂囦欢琚叾浠栫▼搴忓崰鐢紝璇峰叧闂?Excel 鍚庨噸璇曘€?
            )

            return

        except Exception as e:
            wb.close()

            self.log(f"鉂?鍐欏叆 Excel 澶辫触锛歿e}", "error")

            messagebox.showerror("淇濆瓨澶辫触", f"鍐欏叆鏂囦欢鏃跺嚭閿欙細\n{e}")

            return

        finally:
            try:
                wb.close()

            except:
                pass

        # 鈹€鈹€ 8. 鍚屾鍒?SQLite 瀹℃牳鏁版嵁搴?鈹€鈹€

        try:
            self.log("馃搳 姝ｅ湪鍚屾鍒板鏍告暟鎹簱...", "info")

            # 鏋勯€犻€傚悎 storage 妯″潡鐨?DataFrame锛堢‘淇濇湁璁㈠崟鍙峰垪锛?

            save_df = self.audit_data.copy()

            if "璁㈠崟鍙? not in save_df.columns and "娴佺▼璁㈠崟" in save_df.columns:
                save_df["璁㈠崟鍙?] = save_df["娴佺▼璁㈠崟"]

            if "璁㈠崟鏃ユ湡" not in save_df.columns:
                save_df["璁㈠崟鏃ユ湡"] = save_df.get("璁㈠崟鏃ユ湡", "")

            self.audit_presenter.save_audit_back(auditor=auditor)

            self.log("   鏁版嵁搴撳悓姝ユ垚鍔?, "info")

        except Exception as e:
            self.log(f"鈿?瀹℃牳鏁版嵁搴撳悓姝ュけ璐ワ紙涓嶅奖鍝?Excel 淇濆瓨锛夛細{e}", "warn")

        # 鈹€鈹€ 9. 鏈€缁堝弽棣?鈹€鈹€

        self.log(
            f"鉁?瀹℃牳缁撴灉宸蹭繚瀛橈細Excel 鍐欏叆 {saved_count} 琛岋紝澶囦唤 {backup_name}",
            "success",
        )

        messagebox.showinfo(
            "淇濆瓨鎴愬姛",
            f"瀹℃牳缁撴灉宸插啓鍏ュ師濮嬫枃浠?{saved_count} 琛屻€俓n"
            f"鏂板鍒楋細瀹℃牳鐘舵€?/ 瀹℃牳澶囨敞 / 瀹℃牳浜?/ 瀹℃牳鏃堕棿\n"
            f"鍘熷澶囦唤锛歿backup_name}",
        )

    def _batch_export(self, event=None):
        """鎵归噺瀵煎嚭閫変腑琛屼负Excel鎴朇SV"""

        selected = self.audit_tree.selection()

        if not selected:
            messagebox.showwarning("鎻愮ず", "璇峰厛閫夋嫨瑕佸鍑虹殑琛?)

            return

        file_path = filedialog.asksaveasfilename(
            title="瀵煎嚭閫変腑琛?,
            defaultextension=".xlsx",
            filetypes=[
                ("Excel 鏂囦欢", "*.xlsx"),
                ("CSV 鏂囦欢", "*.csv"),
                ("鎵€鏈夋枃浠?, "*.*"),
            ],
        )

        if not file_path:
            return

        columns = self.audit_tree["columns"]

        export_data = []

        for item in selected:
            row_values = [self.audit_tree.set(item, col) for col in columns]

            export_data.append(row_values)

        try:
            if file_path.endswith(".csv"):
                import csv

                with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.writer(f)

                    writer.writerow(columns)

                    writer.writerows(export_data)

            else:
                pd.DataFrame(export_data, columns=columns).to_excel(
                    file_path, index=False, engine="openpyxl"
                )

            messagebox.showinfo(
                "瀵煎嚭鎴愬姛", f"宸叉垚鍔熷鍑?{len(export_data)} 琛屾暟鎹埌\n{file_path}"
            )

        except Exception as e:
            messagebox.showerror("瀵煎嚭澶辫触", f"瀵煎嚭鏃跺彂鐢熼敊璇細{str(e)}")

    def _copy_wechat_draft(self):
        """灏嗛€変腑琛岀敓鎴愬井淇¤崏绋垮苟澶嶅埗鍒板壀璐存澘"""

        selected = self.audit_tree.selection()

        if not selected:
            messagebox.showwarning("鎻愮ず", "璇峰厛閫夋嫨瑕佺敓鎴愯崏绋跨殑琛?)

            return

        cols = self.audit_tree["columns"]

        lines = [self.config.get("wechat.draft_title", "銆愭枡鎺ф寚浠ゃ€?), ""]

        for i, item in enumerate(selected, 1):
            vals = self.audit_tree.item(item, "values")

            data = dict(zip(cols, vals))

            order_no = data.get("order_date", "")

            mat_name = data.get("name", "")

            dev_rate = data.get("dev_rate", "")

            status = data.get("status", "")

            remark = data.get("remark", "")

            code = data.get("code", "")

            # 绠€娲佹牸寮忥細搴忓彿. 鐗╂枡 鍋忓樊鐜?鐘舵€?

            line = f"{i}. {mat_name}锛坽code}锛夊亸宸畕dev_rate} {status}"

            if remark and remark.strip():
                line += f"\n   澶囨敞锛歿remark}"

            lines.append(line)

        lines.append("")

        lines.append(f"鍏?{len(selected)} 鏉?| 璇风‘璁ゅ悗澶勭悊")

        draft = "\n".join(lines)

        self.root.clipboard_clear()

        self.root.clipboard_append(draft)

        self.log(f"馃搵 宸插鍒?{len(selected)} 鏉″井淇¤崏绋垮埌鍓创鏉?, "info")

        messagebox.showinfo(
            "澶嶅埗鎴愬姛", f"宸插鍒?{len(selected)} 鏉℃寚浠ゅ埌鍓创鏉匡紝鍙洿鎺ョ矘璐村埌寰俊"
        )
