"""CLI entrypoint for running economy simulations."""

from __future__ import annotations

import logging
import sys

import click

logger = logging.getLogger(__name__)


@click.command()
@click.argument("input_csv", type=click.Path(exists=True))
@click.argument("config_csv", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default=None, help="Output CSV path")
@click.option("--threshold", "-t", type=float, default=100.0, help="Reward threshold")
@click.option("--churn-boost", "-c", type=float, default=1.3, help="Churn boost multiplier")
@click.option("--seed", "-s", type=int, default=None, help="Random seed for reproducibility")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def main(
    input_csv: str,
    config_csv: str,
    output: str | None,
    threshold: float,
    churn_boost: float,
    seed: int | None,
    verbose: bool,
) -> None:
    """Run a coin flip economy simulation.

    INPUT_CSV: Path to player data CSV (user_id, rolls_sink, avg_multiplier, about_to_churn)

    CONFIG_CSV: Path to config CSV (Input/Value format with probabilities and point values)
    """
    # Lazy imports to keep startup fast
    from src.application.run_simulation import RunSimulationUseCase
    from src.domain.models.coin_flip import CoinFlipConfig
    from src.domain.simulators.coin_flip import CoinFlipSimulator
    from src.infrastructure.readers.local_reader import LocalDataReader
    from src.infrastructure.writers.local_writer import LocalDataWriter

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(message)s",
    )

    try:
        # Read config and create CoinFlipConfig
        reader = LocalDataReader()
        config_raw = reader.read_config(config_csv)
        # from_csv_dict expects string values; reader parses to int/float,
        # so convert back to strings for the CSV parser.
        config_dict = {k: str(v) for k, v in config_raw.items()}
        config = CoinFlipConfig.from_csv_dict(
            config_dict, threshold=threshold, churn_boost=churn_boost
        )

        # Create use case with DI wiring
        writer = LocalDataWriter() if output else None
        use_case = RunSimulationUseCase(
            reader=reader,
            simulator=CoinFlipSimulator(),
            writer=writer,
        )

        # Execute simulation pipeline
        result = use_case.execute(
            player_source=input_csv,
            config=config,
            output_destination=output,
            seed=seed,
        )

        # Print summary
        summary = result.to_summary_dict()
        click.echo(f"Total interactions: {summary['total_interactions']:,}")
        click.echo(f"Total points: {summary['total_points']:,.2f}")
        click.echo(
            f"Players above threshold ({threshold}): " f"{summary['players_above_threshold']:,}"
        )

        # Print distribution
        dist = result.get_distribution()
        click.echo("\nSuccess distribution:")
        for key, count in sorted(dist.items()):
            click.echo(f"  {key}: {count:,}")

        if output:
            click.echo(f"\nResults written to: {output}")

    except (ValueError, FileNotFoundError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"Unexpected error: {exc}", err=True)
        logger.debug("Traceback:", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
