"""CLI 命令行入口"""

from datetime import datetime, timedelta

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from stock_explorer import __version__
from stock_explorer.config.settings import get_config
from stock_explorer.data.cache import get_cache
from stock_explorer.logging.logger import setup_logging
from stock_explorer.monitor.notifier import create_notifier_manager
from stock_explorer.monitor.scanner import get_scanner
from stock_explorer.signal.registry import SignalRegistry

# 设置全局日志
setup_logging()

app = typer.Typer(
    name="stock_explorer",
    help="A股市场实时检测投资信号系统",
    add_completion=False,
)

console = Console()


@app.command("config")
def show_config(
    path: str = typer.Option("config/config.yaml", "--path", "-p", help="配置文件路径"),
):
    """显示配置文件内容"""
    from pathlib import Path

    config_path = Path(path)
    if config_path.exists():
        console.print(f"[green]配置文件内容 ({path}):[/green]")
        console.print(config_path.read_text())
    else:
        console.print(f"[red]配置文件不存在: {path}[/red]")
        raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="显示版本号"),
    config: bool = typer.Option(False, "--config", "-c", help="显示配置文件内容"),
    config_path: str = typer.Option("config/config.yaml", "--config-path", help="配置文件路径"),
    help: bool = typer.Option(False, "--help", "-h", help="显示帮助信息"),
):
    """A股市场实时检测投资信号系统"""
    from pathlib import Path

    if help:
        console.print(ctx.get_help())
        raise typer.Exit()

    if version:
        console.print(f"[bold]StockExplorer[/bold] v{__version__}")
        raise typer.Exit()

    if config or ctx.invoked_subcommand is None:
        path = Path(config_path)
        if path.exists():
            console.print("[green]配置文件内容:[/green]")
            console.print(path.read_text())
        else:
            console.print(f"[red]配置文件不存在: {path}[/red]")
        raise typer.Exit()


@app.command()
def backtest(
    symbols: str = typer.Option(..., "--symbol", "-s", help="股票代码,分隔"),
    strategies: str = typer.Option(..., "--strategy", help="策略名称,分隔"),
    start: str = typer.Option(..., "--start", help="开始日期 YYYY-MM-DD"),
    end: str = typer.Option(..., "--end", help="结束日期 YYYY-MM-DD"),
    capital: float = typer.Option(100000, "--capital", help="初始资金"),
):
    """运行回测"""
    from stock_explorer.backtest.analyzer import PerformanceAnalyzer
    from stock_explorer.backtest.engine import BacktestEngine

    console.print("[bold]回测功能[/bold]")
    console.print(f"股票: {symbols}")
    console.print(f"策略: {strategies}")
    console.print(f"时间: {start} ~ {end}")
    console.print(f"资金: {capital}")

    symbol_list = [s.strip() for s in symbols.split(",")]
    strategy_list = [s.strip() for s in strategies.split(",")]

    console.print("\n[cyan]正在获取数据...[/cyan]")
    engine = BacktestEngine(initial_capital=capital)

    console.print("[cyan]正在执行回测...[/cyan]")
    result = engine.run(
        symbols=symbol_list,
        start_date=start,
        end_date=end,
        strategy_name=",".join(strategy_list),
    )

    analyzer = PerformanceAnalyzer(initial_capital=capital)
    metrics = analyzer.analyze(result.trades, result.equity_curve)
    report = analyzer.generate_report(metrics)

    console.print("\n" + report)


@app.command("monitor-hs300")
def monitor_hs300(
    strategies: str = typer.Option("golden_cross,limit_up", "--strategy", help="策略名称,分隔"),
    interval: int = typer.Option(5, "--interval", "-i", help="扫描间隔(秒)"),
    count: int = typer.Option(1, "--count", "-n", help="扫描次数"),
    show_top: int = typer.Option(10, "--show-top", "-s", help="显示前 N 只股票的数据"),
):
    """沪深300重点监控"""
    console.print(f"[bold]沪深300监控[/bold] - 策略: {strategies}, 间隔: {interval}秒")

    scanner = get_scanner()
    config = get_config()
    notifier = create_notifier_manager(config.alert.model_dump())

    strategy_list = strategies.split(",")

    for i in range(count):
        console.print(f"\n[cyan]第 {i + 1} 次扫描[/cyan]")

        # 获取 HS300 成分股列表
        hs300_list = scanner._get_hs300_list()
        if hs300_list:
            console.print(f"[dim]HS300 成分股数量：{len(hs300_list)}[/dim]")

        signals = scanner.scan_hs300(strategy_list, show_top=show_top)

        if signals:
            for signal in signals:
                notifier.notify(signal)
        else:
            console.print("[dim]未检测到信号[/dim]")

        if i < count - 1:
            import time

            time.sleep(interval)


@app.command("monitor-all")
def monitor_all(
    strategies: str = typer.Option("limit_up,volume_surge", "--strategy", help="策略名称,分隔"),
    interval: int = typer.Option(30, "--interval", "-i", help="扫描间隔(秒)"),
    count: int = typer.Option(1, "--count", "-n", help="扫描次数"),
    show_top: int = typer.Option(10, "--show-top", "-s", help="显示前 N 只股票的数据"),
):
    """全市场扫描"""
    console.print(f"[bold]全市场监控[/bold] - 策略: {strategies}, 间隔: {interval}秒")

    scanner = get_scanner()
    config = get_config()
    notifier = create_notifier_manager(config.alert.model_dump())

    strategy_list = strategies.split(",")

    for i in range(count):
        console.print(f"\n[cyan]第 {i + 1} 次扫描[/cyan]")

        # 获取全市场股票列表
        market_stocks = scanner._get_market_stocks()
        if market_stocks:
            console.print(f"[dim]全市场股票数量：{len(market_stocks)}[/dim]")

        signals = scanner.scan_all(strategy_list, show_top=show_top)

        if signals:
            for signal in signals:
                notifier.notify(signal)
        else:
            console.print("[dim]未检测到信号[/dim]")

        if i < count - 1:
            import time

            time.sleep(interval)


@app.command("monitor-industry")
def monitor_industry(
    industry: str = typer.Option(..., "--industry", help="行业名称"),
    strategies: str = typer.Option("limit_up,volume_surge", "--strategy", help="策略名称,分隔"),
    interval: int = typer.Option(30, "--interval", "-i", help="扫描间隔(秒)"),
    count: int = typer.Option(1, "--count", "-n", help="扫描次数"),
    show_top: int = typer.Option(10, "--show-top", "-s", help="显示前 N 只股票的数据"),
):
    """行业板块监控"""
    console.print(f"[bold]行业监控[/bold] - 行业: {industry}, 策略: {strategies}")

    scanner = get_scanner()
    config = get_config()
    notifier = create_notifier_manager(config.alert.model_dump())

    strategy_list = strategies.split(",")

    for i in range(count):
        console.print(f"\n[cyan]第 {i + 1} 次扫描[/cyan]")

        # 获取行业成分股
        constituents = scanner.fetcher.fetch_stock_board_industry_cons(industry)
        if not constituents.empty:
            console.print(f"[dim]{industry} 成分股数量：{len(constituents)}[/dim]")

        signals = scanner.scan_industry(industry, strategy_list, show_top=show_top)

        if signals:
            for signal in signals:
                notifier.notify(signal)
        else:
            console.print("[dim]未检测到信号[/dim]")

        if i < count - 1:
            import time

            time.sleep(interval)


@app.command("list-strategies")
def list_strategies():
    """列出所有可用策略"""
    console.print("[bold]可用策略列表:[/bold]")

    registry = SignalRegistry()
    strategies = registry.list_all()

    table = Table(show_header=True)
    table.add_column("策略名称", style="cyan")
    table.add_column("信号类型", style="green")

    for name in strategies:
        detector = registry.get(name)
        if detector:
            table.add_row(name, detector.signal_type.value)

    console.print(table)


@app.command("data-hs300")
def data_hs300(clear_cache: bool = typer.Option(False, "--clear-cache", help="清空沪深300成分股缓存")):
    """获取沪深300成分股"""
    if clear_cache:
        console.print("[bold]清空沪深300成分股缓存:[/bold]")
        cache = get_cache()
        key = cache.key_generator.generate_key("hs300", "list")
        cache.invalidate(key)
        console.print("[green]✅ 沪深300成分股缓存已清空[/green]")
        return

    console.print("[bold]沪深300成分股:[/bold]")

    scanner = get_scanner()
    hs300_list = scanner._get_hs300_list()

    table = Table(show_header=True)
    table.add_column("代码", style="cyan")
    table.add_column("名称", style="green")
    table.add_column("交易所", style="yellow")
    table.add_column("指数代码", style="green")
    table.add_column("指数名称", style="cyan")
    table.add_column("日期", style="yellow")

    for item in hs300_list:
        # 使用正确的键名
        code = item.get("成分券代码", "")
        name = item.get("成分券名称", "")
        exchange = item.get("交易所", "")
        index_code = item.get("指数代码", "")
        index_name = item.get("指数名称", "")
        date = str(item.get("日期", ""))
        table.add_row(code, name, exchange, index_code, index_name, date)

    console.print(table)
    console.print(f"\n[dim]共 {len(hs300_list)} 只股票[/dim]")


@app.command("data-industry")
def data_industry(
    detail: bool = typer.Option(False, "--detail", "-d", help="显示完整详细信息"),
    top: int = typer.Option(10, "--top", "-t", help="显示前 N 行详情（仅在 detail 模式下有效）"),
    clear_cache: bool = typer.Option(False, "--clear-cache", help="清空行业数据缓存"),
):
    """获取行业列表"""
    if clear_cache:
        console.print("[bold]清空行业数据缓存:[/bold]")
        cache = get_cache()
        key_list = cache.key_generator.generate_key("industry", "list")
        key_data = cache.key_generator.generate_key("industry", "data")
        cache.invalidate(key_list)
        cache.invalidate(key_data)
        console.print("[green]✅ 行业数据缓存已清空[/green]")
        return

    console.print("[bold]行业板块列表:[/bold]")

    scanner = get_scanner()
    cache = get_cache()

    # 尝试从缓存获取完整数据
    cached_data = cache.get_industry_data()
    if cached_data:
        # 使用缓存的完整数据
        df = pd.DataFrame(cached_data)
    else:
        # 从 scanner 获取行业列表（会触发数据获取和缓存）
        industry_list = scanner.get_industry_list()
        if not industry_list:
            console.print("[red]❌ 未获取到行业数据[/red]")
            return
        # 再次尝试获取完整数据
        cached_data = cache.get_industry_data()
        df = pd.DataFrame(cached_data) if cached_data else pd.DataFrame({"板块名称": industry_list})

    if df.empty:
        console.print("[dim]未获取到行业数据[/dim]")
        return

    if detail:
        # 详细模式：显示前 N 行的完整数据
        console.print(f"[cyan]显示前 {top} 条详细数据:[/cyan]\n")
        for idx, row in df.head(top).iterrows():
            console.print(f"[bold green]第 {idx + 1} 条[/bold green]")
            for col in df.columns:
                value = row[col]
                console.print(f"  [yellow]{col}:[/yellow] {value}")
            console.print()
        console.print(f"[dim]共 {len(df)} 个行业板块，仅显示前 {top} 条详情[/dim]")
    else:
        # 简洁模式：只显示关键列
        console.print("[dim]提示：使用 --detail 参数查看完整数据[/dim]\n")

        table = Table(
            show_header=True, show_lines=True, row_styles=["", "dim"], collapse_padding=True
        )

        # 简洁模式只显示关键列
        key_columns = [
            "排名",
            "板块名称",
            "板块代码",
            "最新价",
            "涨跌幅",
            "换手率",
            "总市值",
            "领涨股票",
            "领涨股票-涨跌幅",
        ]
        column_configs = {
            "排名": {"justify": "right", "width": 5},
            "板块名称": {"style": "green", "width": 20, "no_wrap": True, "overflow": "ellipsis"},
            "板块代码": {"style": "yellow", "width": 8},
            "最新价": {"justify": "right", "width": 10, "no_wrap": True},
            "涨跌幅": {"justify": "right", "width": 8, "no_wrap": True},
            "换手率": {"justify": "right", "width": 8, "no_wrap": True},
            "总市值": {"justify": "right", "width": 12, "no_wrap": True},
            "领涨股票": {"style": "cyan", "width": 10, "no_wrap": True, "overflow": "ellipsis"},
            "领涨股票-涨跌幅": {"justify": "right", "width": 14, "no_wrap": True},
        }

        for col in key_columns:
            if col in df.columns:
                config = column_configs.get(col, {})
                table.add_column(str(col), header_style="bold cyan", **config)

        # 转换总市值为亿单位
        def format_market_cap(value):
            try:
                # 转换为浮点数
                num = float(value)
                # 转换为亿为单位
                return f"{num / 100000000:.2f}亿"
            except (ValueError, TypeError):
                return str(value)

        for _, row in df.iterrows():
            values = []
            for col in key_columns:
                if col not in df.columns:
                    continue
                value = row[col]
                # 如果是总市值，转换为亿单位
                if col == "总市值":
                    values.append(format_market_cap(value))
                else:
                    values.append(str(value))
            table.add_row(*values)

        console.print(table)
        console.print(f"\n[dim]共 {len(df)} 个行业板块[/dim]")



@app.command("list-signals")
def signals_list(
    start: str | None = typer.Option(None, "--start", help="开始日期 YYYY-MM-DD"),
    end: str | None = typer.Option(None, "--end", help="结束日期 YYYY-MM-DD"),
    limit: int = typer.Option(20, "--limit", "-n", help="显示数量"),
):
    """查询历史信号"""
    from stock_explorer.data.storage import get_database

    db = get_database()

    start_date = start or (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date = end or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    df = db.get_signals(start_date=start_date, end_date=end_date, limit=limit)

    if df.empty:
        console.print("[dim]未找到历史信号[/dim]")
        return

    table = Table(show_header=True)
    table.add_column("时间", style="cyan")
    table.add_column("股票", style="yellow")
    table.add_column("方向", style="green")
    table.add_column("信号", style="magenta")

    for _, row in df.iterrows():
        table.add_row(
            str(row["timestamp"])[:19],
            f"{row['symbol']} {row['name']}",
            row["direction"],
            row["signal_type"],
        )

    console.print(table)


@app.command("daemon")
def daemon_start(
    background: bool = typer.Option(False, "--background", "-b", help="后台运行"),
):
    """启动常驻服务"""
    from stock_explorer.service.manager import ServiceConfig, ServiceManager

    config = ServiceConfig(
        scan_interval_hs300=5,
        scan_interval_market=30,
        scan_interval_industry=30,
        enable_hs300_scan=True,
        enable_market_scan=False,
        enable_industry_scan=False,
    )

    manager = ServiceManager(config)

    console.print("[bold green]正在启动信号检测服务...[/bold green]")
    console.print(f"  HS300扫描: 启用 (间隔 {config.scan_interval_hs300}秒)")
    console.print(
        f"  全市场扫描: {'启用' if config.enable_market_scan else '禁用'} (间隔 {config.scan_interval_market}秒)"
    )
    console.print(
        f"  行业扫描: {'启用' if config.enable_industry_scan else '禁用'} (间隔 {config.scan_interval_industry}秒)"
    )

    try:
        manager.start()
        console.print("[bold green]服务已启动，按 Ctrl+C 停止[/bold green]")

        import time

        try:
            while manager.status.value == "running":
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]正在停止服务...[/yellow]")
            manager.stop()
            console.print("[green]服务已停止[/green]")

    except Exception as e:
        console.print(f"[bold red]服务启动失败: {e}[/bold red]")
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
