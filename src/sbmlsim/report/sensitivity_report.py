"""Quarto-based sensitivity analysis report generator."""

import subprocess
from pathlib import Path
from typing import Union

import pandas as pd


class QuartoSensitivityReport:
    """
    Generates an interactive HTML report from simulation results.
    Accepts either a raw pandas DataFrame, an sbmlsim XResult, or a SensitivityResult.
    """

    def __init__(self, data: Union[pd.DataFrame, "XResult"], output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.data_path = self.output_dir / "sensitivity_data.csv"
        self.qmd_path = self.output_dir / "report.qmd"

        # POLYMORPHISM: Handle different input types
        if hasattr(data, "to_dataframe"):
            # Handles SensitivityResult or similar objects with to_dataframe method
            self.df = data.to_dataframe()
        elif hasattr(data, "xds"):
            # Handles the XResult object (Legacy/Low-level)
            self.df = self._extract_from_xresult(data)
        elif isinstance(data, pd.DataFrame):
            # Handles raw DataFrames
            self.df = data
        else:
            raise TypeError(
                "Input must be XResult, SensitivityResult, or pandas DataFrame"
            )

    def _extract_from_xresult(self, xres) -> pd.DataFrame:
        """Helper to convert XResult to DataFrame and strip units."""
        df = xres.xds.to_dataframe().reset_index()
        return self._strip_units(df)

    def _strip_units(self, df: pd.DataFrame) -> pd.DataFrame:
        """Strip pint Unit objects from DataFrame columns, keeping only magnitudes."""
        for col in df.columns:
            # Check the first item to see if it's a Quantity (has .magnitude)
            if len(df) > 0 and hasattr(df[col].iloc[0], "magnitude"):
                df[col] = df[col].apply(lambda x: x.magnitude)
        return df

    def _generate_qmd(self, df_columns) -> str:
        """Generates the Quarto Markdown content."""

        # Heuristic: Find the likely X-axis (time or the first column)
        # and assume the rest are data columns
        x_axis = df_columns[0]
        y_cols = list(df_columns[1:])

        return f'''---
title: "Sensitivity Analysis Report"
format:
  html:
    code-fold: true
    toc: true
    theme: cosmo
---

## Overview

This report provides an interactive visualization of the sensitivity analysis results.
You can zoom, pan, and hover over the data points below.

```{{python}}
#| label: fig-interactive
#| fig-cap: "Interactive Sensitivity Plot"

import pandas as pd
import plotly.express as px

# 1. Load the pre-computed data
df = pd.read_csv("{self.data_path.name}")

# 2. Create Interactive Plot
# We plot all result columns against the first dimension (usually time or parameter)
fig = px.line(
    df, 
    x="{x_axis}", 
    y={y_cols}, 
    title="Sensitivity Analysis Results",
    labels={{"{x_axis}": "{x_axis}", "value": "Concentration / Sensitivity"}}
)

fig.update_layout(autosize=True)
fig.show()
```

## Data Summary

```{{python}}
#| label: tbl-summary
#| tbl-cap: "First 5 rows of data"
from IPython.display import display, Markdown
display(df.head())
```
'''

    def build(self):
        """Build the Quarto report."""
        print("1. Processing data and stripping units...")
        # Ensure units are stripped before saving
        self.df = self._strip_units(self.df)
        self.df.to_csv(self.data_path, index=False)

        print(f"2. Writing Quarto template to {self.qmd_path}...")
        with open(self.qmd_path, "w") as f:
            f.write(self._generate_qmd(self.df.columns))

        print("3. Rendering HTML...")
        try:
            # Check if quarto is installed
            subprocess.run(
                ["quarto", "--version"], check=True, stdout=subprocess.DEVNULL
            )

            # Render
            subprocess.run(["quarto", "render", str(self.qmd_path)], check=True)
            print(
                f"\nSUCCESS! Interactive report generated at:\n   {self.output_dir / 'report.html'}"
            )
        except FileNotFoundError:
            print(
                "\nERROR: 'quarto' command not found. Please install Quarto CLI (https://quarto.org)."
            )
        except subprocess.CalledProcessError as e:
            print(f"\nERROR: Quarto rendering failed.\n{e}")
