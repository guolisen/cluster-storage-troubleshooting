import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn # Keep if progress bars are used by UI

class TroubleshootingUI:
    def __init__(self, console: Console, file_console: Console):
        self.console = console
        self.file_console = file_console # For logging rich content to file if needed

    def display_initial_banner(self, pod_name: str, namespace: str, volume_path: str, start_time_str: str):
        """Displays the initial troubleshooting banner."""
        self.console.print("\n")
        self.console.print(Panel(
            f"[bold white]Starting troubleshooting for Pod: [green]{namespace}/{pod_name}[/green]\n"
            f"Volume Path: [blue]{volume_path}[/blue]\n"
            f"Start Time: [yellow]{start_time_str}[/yellow]",
            title="[bold cyan]KUBERNETES VOLUME TROUBLESHOOTING",
            border_style="cyan",
            padding=(1, 2)
        ))

    def display_investigation_plan(self, plan_text: str):
        """Displays the investigation plan."""
        self.console.print("\n")
        self.console.print(Panel(
            f"[bold white]{plan_text}",
            title="[bold blue]INVESTIGATION PLAN",
            border_style="blue",
            padding=(1, 2)
        ))

    def display_fix_plan(self, plan_text: str):
        """Displays the fix plan from Phase 1 analysis."""
        self.console.print("\n")
        self.console.print(Panel(
            f"[bold white]{plan_text}",
            title="[bold blue]FIX PLAN", # Or "Analysis Result" / "Root Cause Analysis"
            border_style="blue",
            padding=(1, 2)
        ))

    def display_event_summary(self, summary_text: str):
        """Displays the event summary from Phase 1 analysis."""
        self.console.print(Panel(
            f"[bold white]{summary_text}",
            title="[bold magenta]Event Summary",
            border_style="magenta",
            padding=(1, 2)
        ))

    def display_phase2_skipped(self):
        """Displays a message indicating Phase 2 was skipped."""
        self.console.print("\n")
        self.console.print(Panel(
            "[bold white]Phase 2 skipped - no remediation needed or manual intervention required",
            title="[bold yellow]PHASE 2: SKIPPED",
            border_style="yellow",
            padding=(1, 2)
        ))

    def display_remediation_start_panel(self):
        """Displays a panel indicating the start of the remediation phase."""
        self.console.print("\n")
        self.console.print(Panel(
            "[yellow]Starting remediation with LangGraph...\nThis may take a few minutes to complete.",
            title="[bold green]Remediation Phase",
            border_style="green"
        ))

    def display_remediation_complete(self):
        """Displays a message when remediation is complete."""
        self.console.print("[green]Remediation complete![/green]")

    def display_remediation_timeout(self):
        """Displays a message when remediation times out."""
        self.console.print("[red]Remediation timed out![/red]")

    def display_remediation_failed(self, error_message: str):
        """Displays a message when remediation fails."""
        self.console.print(f"[red]Remediation failed: {error_message}[/red]")


    def display_final_summary(self, results: dict, phase1_final_response: str, remediation_result: str):
        """Displays the final troubleshooting summary table and root cause/resolution."""
        summary_table = Table(
            title="[bold]TROUBLESHOOTING SUMMARY",
            header_style="bold cyan",
            border_style="blue",
        )
        summary_table.add_column("Phase", style="dim")
        summary_table.add_column("Duration", justify="right")
        summary_table.add_column("Status", justify="center")

        summary_table.add_row(
            "Phase 0: Information Collection",
            f"{results['phases']['phase_0_collection']['duration']:.2f}s",
            "[green]Completed[/green]" if results['phases']['phase_0_collection']['status'] == 'completed' else "[red]Failed[/red]"
        )

        plan_phase_status_str = "[green]Completed[/green]" if results["phases"].get("plan_phase", {}).get("status") == "completed" else "[red]Failed[/red]"
        plan_phase_duration = results["phases"].get("plan_phase", {}).get("duration", 0)
        summary_table.add_row(
            "Plan Phase: Investigation Plan",
            f"{plan_phase_duration:.2f}s",
            plan_phase_status_str
        )

        phase1_status_str = "[green]Completed[/green]" if results['phases']['phase_1_analysis']['status'] == 'completed' else "[red]Failed[/red]"
        summary_table.add_row(
            "Phase 1: ReAct Investigation",
            f"{results['phases']['phase_1_analysis']['duration']:.2f}s",
            phase1_status_str
        )

        phase2_data = results['phases']['phase_2_remediation']
        phase2_status_str = "[yellow]Skipped[/yellow]"
        if phase2_data['status'] == 'completed':
            phase2_status_str = "[green]Completed[/green]"
        elif phase2_data['status'] == 'failed': # Assuming a 'failed' status is possible
            phase2_status_str = "[red]Failed[/red]"

        summary_table.add_row(
            "Phase 2: Remediation",
            f"{phase2_data['duration']:.2f}s",
            phase2_status_str
        )

        total_status_str = "[bold green]Completed[/bold green]" if results['status'] == 'completed' else "[bold red]Failed[/bold red]"
        summary_table.add_row(
            "Total",
            f"{results['total_duration']:.2f}s",
            total_status_str
        )

        root_cause_str = str(phase1_final_response) if phase1_final_response is not None else "Unknown"
        remediation_result_str = str(remediation_result) if remediation_result is not None else "No result or Phase 2 skipped"

        root_cause_panel = Panel(
            f"[bold yellow]{root_cause_str}",
            title="[bold red]Root Cause / Analysis", # Renamed for clarity
            border_style="red",
            padding=(1, 2),
            safe_box=True
        )
        resolution_panel = Panel(
            f"[bold green]{remediation_result_str}",
            title="[bold blue]Resolution Status / Remediation Output", # Renamed for clarity
            border_style="green",
            padding=(1, 2),
            safe_box=True
        )

        try:
            self.console.print(summary_table)
        except Exception as e:
            self.console.print(f"Error printing rich summary table: {e}")

        self.console.print("\n")
        self.console.print(root_cause_panel)
        self.console.print("\n")
        self.console.print(resolution_panel)

    def display_error_panel(self, message: str, title: str = "[bold red]ERROR[/bold red]"):
        """Displays a generic error panel."""
        self.console.print(Panel(
            f"[bold white]{message}",
            title=title,
            border_style="red",
            padding=(1, 2)
        ))

    def display_info_panel(self, message: str, title: str = "[bold blue]INFO[/bold blue]"):
        """Displays a generic info panel."""
        self.console.print(Panel(
            f"[bold white]{message}",
            title=title,
            border_style="blue",
            padding=(1, 2)
        ))

    def display_exit_message(self, message: str):
        """Displays an exit message."""
        self.console.print(f"[bold red]{message}[/bold red]")

# Example of how progress might be handled if needed by other parts of UI
# This is a placeholder, actual integration depends on where progress is initiated.
_global_progress_instance = None

def get_progress_instance(console: Console):
    """Manages a global rich Progress instance."""
    global _global_progress_instance
    if _global_progress_instance is None:
        _global_progress_instance = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True
        )
        _global_progress_instance.start()
    return _global_progress_instance

def stop_progress_instance():
    """Stops the global rich Progress instance if it's running."""
    global _global_progress_instance
    if _global_progress_instance is not None:
        _global_progress_instance.stop()
        _global_progress_instance = None
