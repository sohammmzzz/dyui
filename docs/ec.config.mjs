// Expressive Code (code blocks) options. Starlight loads this file; it has to be separate from
// astro.config.mjs because the options include a plugin (a function), and the <Code>
// component can only read non-JSON options from here.

// Copy buttons on code blocks: Expressive Code drops the final newline, so a pasted file
// ended mid-line and the next paste joined onto it (`yield part"""Data analyst…`). Every
// non-terminal block now copies with a trailing newline. Terminal blocks are left alone:
// there a trailing newline would run the last command as soon as it is pasted.
const TERMINAL = new Set(["sh", "bash", "shell", "shellscript", "zsh", "console", "shellsession",
  "powershell", "ps", "ps1", "pwsh", "bat", "batch", "cmd"]);
const copyWithNewline = () => ({
  name: "dyui-copy-with-newline",
  hooks: {
    postprocessRenderedBlock: ({ codeBlock, renderData }) => {
      if (TERMINAL.has(codeBlock.language) || codeBlock.props.frame === "terminal") return;
      const visit = (node) => {
        const p = node.properties;
        if (p && typeof p.dataCode === "string" && !p.dataCode.endsWith("\u007f")) p.dataCode += "\u007f";
        (node.children || []).forEach(visit);
      };
      visit(renderData.blockAst);
    },
  },
});

export default {
  plugins: [copyWithNewline()],
  themes: ["github-light", "github-dark-dimmed"],
  styleOverrides: {
    borderRadius: "12px",
    borderColor: "var(--dy-border)",
    codeFontFamily: "var(--dy-font-mono)",
    uiFontFamily: "var(--dy-font)",
    codeFontSize: "13.5px",
    codeLineHeight: "1.7",
    codePaddingBlock: "1rem",
    codePaddingInline: "1.15rem",
    // code sits on the brand surfaces (see --dx-code-* in theme.css), not the syntax theme's own
    codeBackground: "var(--dx-code-bg)",
    frames: {
      shadowColor: "transparent",
      frameBoxShadowCssValue: "none",
      editorBackground: "var(--dx-code-bg)",
      editorTabBarBackground: "var(--dx-code-bar)",
      editorTabBarBorderBottomColor: "var(--dy-border)",
      editorActiveTabBackground: "var(--dx-code-bg)",
      editorActiveTabForeground: "var(--sl-color-white)",
      editorActiveTabBorderColor: "transparent",
      editorActiveTabIndicatorTopColor: "transparent",
      editorActiveTabIndicatorBottomColor: "var(--dx-code-bg)",
      terminalBackground: "var(--dx-code-bg)",
      terminalTitlebarBackground: "var(--dx-code-bar)",
      terminalTitlebarForeground: "var(--sl-color-gray-3)",
      terminalTitlebarBorderBottomColor: "var(--dy-border)",
      terminalTitlebarDotsForeground: "var(--dy-border-strong)",
      terminalTitlebarDotsOpacity: "1",
      inlineButtonBackground: "var(--sl-color-gray-3)",
      inlineButtonForeground: "var(--sl-color-gray-2)",
      inlineButtonBorder: "var(--dy-border-strong)",
    },
  },
};
