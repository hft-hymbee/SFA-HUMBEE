const textStyle = (sizeVar, lineVar, weightVar, theme) => ({
  color: theme.palette.text.primary,
  display: "block",
  fontSize: `var(${sizeVar})`,
  fontStyle: "normal",
  fontWeight: `var(${weightVar})`,
  lineHeight: `var(${lineVar})`,
});

export const getTypography = (theme) => ({
  fontFamily: "var(--font-family-base, Lato, sans-serif)",

  display: textStyle("--text-display-size", "--text-display-line", "--text-display-weight", theme),
  title: textStyle("--text-title-size", "--text-title-line", "--text-title-weight", theme),
  h1: textStyle("--text-h1-size", "--text-h1-line", "--text-h1-weight", theme),
  h2: textStyle("--text-h2-size", "--text-h2-line", "--text-h2-weight", theme),
  h3: textStyle("--text-h3-size", "--text-h3-line", "--text-h3-weight", theme),

  labelM: textStyle("--text-label-sm-size", "--text-label-sm-line", "--text-label-sm-weight", theme),
  labelK: textStyle("--text-label-size", "--text-label-line", "--text-label-weight", theme),
  labelS: textStyle("--text-label-xs-size", "--text-label-xs-line", "--text-label-xs-weight", theme),
  labelD: textStyle("--text-label-size", "--text-label-line", "--text-label-weight", theme),
  labelF: textStyle("--text-label-xs-size", "--text-label-xs-line", "--text-label-xs-weight", theme),

  body1: textStyle("--text-body-size", "--text-body-line", "--text-body-weight", theme),
  bodyL: textStyle("--text-body-size", "--text-body-line", "--text-body-strong-weight", theme),
  bodyM: textStyle("--text-body-sm-size", "--text-body-sm-line", "--text-body-strong-weight", theme),

  p1: textStyle("--text-body-size", "--text-body-line", "--text-body-weight", theme),
  p2: textStyle("--text-body-sm-size", "--text-body-sm-line", "--text-body-strong-weight", theme),
  p3: textStyle("--text-body-sm-size", "--text-body-sm-line", "--text-body-sm-weight", theme),
  p4: textStyle("--text-caption-size", "--text-caption-line", "--text-caption-weight", theme),
  caption: textStyle("--text-caption-size", "--text-caption-line", "--text-caption-weight", theme),
  overline: {
    ...textStyle("--text-overline-size", "--text-overline-line", "--text-overline-weight", theme),
    letterSpacing: "var(--text-overline-tracking)",
    textTransform: "uppercase",
  },
});
