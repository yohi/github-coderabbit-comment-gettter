#!/usr/bin/env python3
"""
pytest実行時のメモリ使用量監視スクリプト
"""

import time
import sys
import argparse
import subprocess
import os
from datetime import datetime

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("⚠️ psutil not available, using basic monitoring")

# メモリ使用量の閾値定数 (MB)
MEMORY_DANGER_MB = 10240   # 10 GiB / 10240 MB
MEMORY_WARNING_MB = 5120   # 5 GiB / 5120 MB

def get_system_memory_basic():
    """基本的なシステムメモリ情報を取得（psutil不要）"""
    try:
        result = subprocess.run(['free', '-h'], capture_output=True, text=True)
        return result.stdout
    except Exception:
        return "メモリ情報取得不可"

def monitor_pytest_memory(duration=300, interval=5):
    """pytestプロセスのメモリ使用量を監視"""
    
    if not HAS_PSUTIL:
        print("📊 基本メモリ監視モード")
        print(get_system_memory_basic())
        return
    
    print(f"🔍 pytest プロセス監視開始 (期間: {duration}秒, 間隔: {interval}秒)")
    print("=" * 80)
    
    start_time = time.time()
    max_memory = 0
    pytest_processes = []
    
    while time.time() - start_time < duration:
        current_time = datetime.now().strftime("%H:%M:%S")
        pytest_found = False
        
        # すべてのプロセスをチェック
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline']):
            try:
                # pytestプロセスを特定
                proc_name = proc.info.get('name', '').lower() if proc.info.get('name') else ''
                cmdline = proc.info.get('cmdline') or []
                
                # pytestプロセスの判定条件を改善
                is_pytest_process = False
                
                # 1. プロセス名に"pytest"が含まれる場合（直接実行）
                if 'pytest' in proc_name:
                    is_pytest_process = True
                # 2. プロセス名に"python"が含まれ、コマンドライン引数に"pytest"がある場合
                elif 'python' in proc_name and cmdline:
                    is_pytest_process = any('pytest' in str(arg) for arg in cmdline if arg is not None)
                
                if is_pytest_process:
                    
                    pytest_found = True
                    memory_mb = proc.info['memory_info'].rss / 1024 / 1024
                    max_memory = max(max_memory, memory_mb)
                    
                    print(f"[{current_time}] PID: {proc.info['pid']:>7} | "
                          f"メモリ: {memory_mb:>8.1f} MB | "
                          f"最大: {max_memory:>8.1f} MB")
                    
                    # 危険レベルのチェック
                    if memory_mb > MEMORY_DANGER_MB:  # 10 GiB / 10240 MB超過
                        print(f"🚨 警告: メモリ使用量が危険レベル ({memory_mb:.1f} MB)")
                    elif memory_mb > MEMORY_WARNING_MB:  # 5 GiB / 5120 MB超過
                        print(f"⚠️  注意: メモリ使用量が高い ({memory_mb:.1f} MB)")
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if not pytest_found:
            print(f"[{current_time}] pytestプロセスが見つかりません...")
        
        time.sleep(interval)
    
    print("=" * 80)
    print(f"✅ 監視完了")
    print(f"📊 最大メモリ使用量: {max_memory:.1f} MB")
    
    if max_memory > MEMORY_DANGER_MB:
        print("🚨 メモリ使用量が非常に高い状態でした。最適化が必要です。")
    elif max_memory > MEMORY_WARNING_MB:
        print("⚠️  メモリ使用量が高めでした。監視を継続してください。")
    else:
        print("✅ メモリ使用量は正常範囲内でした。")

def show_current_memory_status():
    """現在のシステムメモリ状況を表示"""
    
    print("📊 現在のシステムメモリ状況")
    print("=" * 50)
    
    if not HAS_PSUTIL:
        print(get_system_memory_basic())
        return
    
    # システム全体のメモリ
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    print(f"🖥️  システムメモリ:")
    print(f"   総量:     {memory.total / 1024**3:.1f} GB")
    print(f"   使用中:   {memory.used / 1024**3:.1f} GB ({memory.percent:.1f}%)")
    print(f"   利用可能: {memory.available / 1024**3:.1f} GB")
    
    print(f"💾 スワップ:")
    print(f"   総量:     {swap.total / 1024**3:.1f} GB")
    print(f"   使用中:   {swap.used / 1024**3:.1f} GB ({swap.percent:.1f}%)")
    
    # pytestプロセスをチェック
    pytest_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline']):
        try:
            # pytestプロセスの判定条件を改善（show_current_memory_status）
            proc_name = proc.info.get('name', '').lower() if proc.info.get('name') else ''
            cmdline = proc.info.get('cmdline') or []
            
            is_pytest_process = False
            
            # 1. プロセス名に"pytest"が含まれる場合（直接実行）
            if 'pytest' in proc_name:
                is_pytest_process = True
            # 2. プロセス名に"python"が含まれ、コマンドライン引数に"pytest"がある場合
            elif 'python' in proc_name and cmdline:
                is_pytest_process = any('pytest' in str(arg) for arg in cmdline if arg is not None)
            
            if is_pytest_process:
                memory_mb = proc.info['memory_info'].rss / 1024 / 1024
                pytest_processes.append((proc.info['pid'], memory_mb))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if pytest_processes:
        print(f"\n🧪 実行中のpytestプロセス:")
        for pid, memory_mb in pytest_processes:
            print(f"   PID {pid}: {memory_mb:.1f} MB")
            if memory_mb > MEMORY_DANGER_MB:
                print(f"      🚨 危険: 非常に高いメモリ使用量")
            elif memory_mb > MEMORY_WARNING_MB:
                print(f"      ⚠️  警告: 高いメモリ使用量")
    else:
        print(f"\n✅ 現在pytestプロセスは実行されていません")

def main():
    parser = argparse.ArgumentParser(description='pytest実行時のメモリ監視ツール')
    parser.add_argument('--monitor', '-m', action='store_true', 
                       help='pytestプロセスの監視を開始')
    parser.add_argument('--status', '-s', action='store_true',
                       help='現在のメモリ状況を表示')
    parser.add_argument('--duration', '-d', type=int, default=300,
                       help='監視時間（秒）[デフォルト: 300]')
    parser.add_argument('--interval', '-i', type=int, default=5,
                       help='チェック間隔（秒）[デフォルト: 5]')
    
    args = parser.parse_args()
    
    if args.status:
        show_current_memory_status()
    elif args.monitor:
        monitor_pytest_memory(args.duration, args.interval)
    else:
        # デフォルトは現在の状況表示
        show_current_memory_status()

if __name__ == "__main__":
    main()