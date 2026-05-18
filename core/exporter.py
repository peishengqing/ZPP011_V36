import shutil
import os
import time
import pandas as pd
from pathlib import Path


class ExcelExporter:
    """
    Excel 导出器（异步支持，进度回调，取消支持，原子化写入）
    """

    @staticmethod
    def export(df, output_path, progress_callback=None, cancel_flag=None):
        """
        导出 DataFrame 到 Excel，支持进度回调和取消

        Args:
            df: 要导出的 DataFrame
            output_path: 输出文件路径（str 或 Path）
            progress_callback: 进度回调函数，接收 (current, total, eta)
            cancel_flag: threading.Event 对象，用于取消操作

        Returns:
            输出文件的 Path 对象
        """
        total_rows = len(df)
        if total_rows == 0:
            raise ValueError("没有数据可导出")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 文件名去重：若已存在则添加 _1, _2 后缀
        stem = output_path.stem
        suffix = output_path.suffix
        counter = 1
        while output_path.exists():
            output_path = output_path.parent / f"{stem}_{counter}{suffix}"
            counter += 1

        temp_path = output_path.with_suffix(suffix + ".tmp")
        start_time = time.time()

        try:
            # 分块模拟处理进度（不实际分块写入 Excel）
            chunk_size = 500
            for start in range(0, total_rows, chunk_size):
                if cancel_flag and cancel_flag.is_set():
                    raise InterruptedError("导出已取消")

                processed = min(start + chunk_size, total_rows)
                if progress_callback:
                    # 计算 ETA，避免除零
                    if processed > 0:
                        elapsed = time.time() - start_time
                        eta = (total_rows - processed) * (elapsed / processed)
                    else:
                        eta = 0
                    progress_callback(processed, total_rows, eta)

                time.sleep(0.01)  # 释放 CPU，模拟处理

            # 一次性写入 Excel（写入速度快，无需分块）
            with pd.ExcelWriter(temp_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')

            # 原子化重命名临时文件为正式文件
            shutil.move(str(temp_path), str(output_path))

        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise e

        return output_path
