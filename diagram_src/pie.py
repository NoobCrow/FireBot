# EDIT these percentages to your team's agreed split, then re-run: python3 pie.py
import matplotlib.pyplot as plt
members = ["Farhan Labib", "Ashik Mahmud", "Prottoy Roy Deep", "Maisha Ahmed"]
share   = [40, 25, 20, 15]
colors  = ["#0046A0", "#2E8B57", "#E67E22", "#C0392B"]
fig, ax = plt.subplots(figsize=(5, 5))
ax.pie(share, labels=members, colors=colors, autopct="%1.0f%%", startangle=90,
       wedgeprops=dict(edgecolor="white", linewidth=2), textprops=dict(fontsize=11))
for t in ax.texts:
    if t.get_text().endswith('%'): t.set_color('white'); t.set_fontweight('bold')
ax.axis("equal")
plt.savefig("../docs/images/fig_contribution_pie.png", dpi=220, bbox_inches="tight")
