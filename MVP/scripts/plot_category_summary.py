import math
import os
import pandas as pd
import matplotlib.pyplot as plt


def main():
    csv_path = os.path.join(
        "data",
        "output",
        "experiments",
        "FINALK RESUTLS",
        "tracker_stat_outputs",
        "category_summary_mean_sd.csv",
    )

    out_dir = os.path.dirname(csv_path)
    out_png = os.path.join(out_dir, "category_summary_mean_sd.png")

    df = pd.read_csv(csv_path)

    # Create a single label for plotting
    df["label"] = df["configuration"].astype(str) + " — " + df["category"].astype(str)

    # Keep only the columns we care about and ensure numeric dtype
    for col in [
        "accuracy_produced_mean",
        "accuracy_produced_sd",
        "overall_accuracy_mean",
        "overall_accuracy_sd",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Sort by overall accuracy for nicer visualization
    df = df.sort_values("overall_accuracy_mean", ascending=False)

    plt.style.use("seaborn-whitegrid")
    fig, axes = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

    x = range(len(df))
    labels = df["label"].tolist()

    # Top: produced accuracy with error bars
    axes[0].bar(
        x,
        df["accuracy_produced_mean"],
        yerr=df["accuracy_produced_sd"],
        capsize=5,
        color=plt.get_cmap("tab10").colors,
    )
    axes[0].set_ylabel("Accuracy of Produced Outputs (%)")
    axes[0].set_title("Produced-output Accuracy (mean ± sd)")
    axes[0].set_ylim(0, 105)

    # Bottom: overall accuracy with error bars
    axes[1].bar(
        x,
        df["overall_accuracy_mean"],
        yerr=df["overall_accuracy_sd"],
        capsize=5,
        color=plt.get_cmap("tab10").colors,
    )
    axes[1].set_ylabel("Overall Accuracy (%)")
    axes[1].set_title("Overall Accuracy (mean ± sd)")
    axes[1].set_ylim(0, 105)

    # X ticks
    plt.xticks(x, labels, rotation=45, ha="right")

    plt.tight_layout()
    fig.savefig(out_png, dpi=200)
    print(f"Saved figure to: {out_png}")


if __name__ == "__main__":
    main()
