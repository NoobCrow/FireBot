# EDIT these percentages to your team's agreed split, then re-run: python3 pie.py
from pathlib import Path
import matplotlib.pyplot as plt

members = ["Farhan Labib", "Ashik Mahmud", "Prottoy Roy Deep", "Maisha Ahmed"]
share = [40, 20, 20, 20]
colors = ["#0046A0", "#2E8B57", "#E67E22", "#C0392B"]

fig, ax = plt.subplots(figsize=(5, 5))
ax.pie(
    share,
    labels=members,
    colors=colors,
    autopct="%1.0f%%",
    startangle=90,
    wedgeprops=dict(edgecolor="white", linewidth=2),
    textprops=dict(fontsize=11),
)
for t in ax.texts:
    if t.get_text().endswith('%'):
        t.set_color('white')
        t.set_fontweight('bold')

ax.axis("equal")
out_path = Path(__file__).resolve().parent.parent / "docs" / "images" / "fig_contribution_pie.png"
plt.savefig(out_path, dpi=220, bbox_inches="tight")
