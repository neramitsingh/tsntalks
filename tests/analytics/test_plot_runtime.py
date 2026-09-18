"""Plot is loaded from a CDN and its DOM is what charts.js decorates. This pins
the two facts charts.js depends on: the globals exist at the pinned versions,
and Plot labels its mark and axis groups with the aria-labels the decorator
selects on. If a version bump changes either, this fails before anything else."""


def test_plot_and_d3_are_present_at_the_pinned_versions(dashboard):
    got = dashboard.evaluate("() => ({ d3: window.d3?.version, plot: typeof window.Plot?.plot })")
    assert got == {"d3": "7.9.0", "plot": "function"}


def test_plot_labels_the_groups_the_decorator_relies_on(dashboard):
    labels = dashboard.evaluate("""() => {
      const svg = Plot.plot({
        width: 300, height: 120,
        x: { type: 'band', domain: ['a', 'b'] },
        y: { grid: true },
        marks: [
          Plot.line([{ x: 'a', y: 1 }, { x: 'b', y: 2 }], { x: 'x', y: 'y' }),
          Plot.barY([{ x: 'a', y: 1 }], { x: 'x', y: 'y' }),
        ],
      });
      return [...svg.querySelectorAll('g[aria-label]')].map((g) => g.getAttribute('aria-label'));
    }""")
    for needed in ("y-grid", "x-axis tick label", "y-axis tick label", "line", "bar"):
        assert needed in labels, f"Plot no longer labels {needed!r}: {labels}"
