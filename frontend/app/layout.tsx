import type { Metadata } from "next";
import { Inter, Spectral, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

// The story editor face. Spectral is a screen-first serif with a large
// x-height - it holds up at 17px over long drafting sessions.
const spectral = Spectral({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-spectral",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono-jb",
  display: "swap",
});

const EXTENSION_GUARD = `(function () {
  var EXT = /(chrome|moz|safari-web)-extension:\\/\\//;
  function fromExtension(stack) {
    if (!stack) return false;
    var lines = String(stack).split("\\n").slice(1);
    return lines.length > 0 && EXT.test(lines[0]);
  }
  window.addEventListener("error", function (e) {
    if (EXT.test(e.filename || "") || fromExtension(e.error && e.error.stack)) {
      e.stopImmediatePropagation(); e.preventDefault();
    }
  }, true);
  window.addEventListener("unhandledrejection", function (e) {
    if (fromExtension(e.reason && e.reason.stack)) {
      e.stopImmediatePropagation(); e.preventDefault();
    }
  }, true);
  var ATTRS = ["bis_skin_checked", "bis_register", "bis_use", "data-bis-config",
               "data-new-gr-c-s-check-loaded", "data-gr-ext-installed", "cz-shortcut-listen"];
  function strip(el) {
    if (!el || el.nodeType !== 1) return;
    for (var i = 0; i < ATTRS.length; i++) if (el.hasAttribute(ATTRS[i])) el.removeAttribute(ATTRS[i]);
    var names = el.getAttributeNames ? el.getAttributeNames() : [];
    for (var j = 0; j < names.length; j++) if (names[j].indexOf("__processed_") === 0) el.removeAttribute(names[j]);
  }
  new MutationObserver(function (records) {
    for (var r = 0; r < records.length; r++) {
      var rec = records[r];
      if (rec.type === "attributes") strip(rec.target);
      else for (var n = 0; n < rec.addedNodes.length; n++) {
        var node = rec.addedNodes[n]; strip(node);
        if (node.querySelectorAll) { var all = node.querySelectorAll("*"); for (var k = 0; k < all.length; k++) strip(all[k]); }
      }
    }
  }).observe(document.documentElement, { attributes: true, attributeFilter: ATTRS, childList: true, subtree: true });
})();`;

export const metadata: Metadata = {
  title: "Story Studio — Human–AI Co-Creative Storytelling",
  description:
    "An educational writing environment where the AI asks instead of answers. ET617 Group 15.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${spectral.variable} ${mono.variable}`}>
      <head>
        {/* Browser extensions interfere with the page in two ways, and the
            Next.js dev overlay shows both as "issues" in a red badge in front
            of participants:
              1. they throw their own errors into the page;
              2. they write attributes into the HTML before React hydrates
                 (Bitdefender's bis_skin_checked, Grammarly, ColorZilla), which
                 React reports as a hydration mismatch.
            This inline script is registered before anything else: it stops
            errors whose source is an extension, and strips the known injected
            attributes as they appear. The app's own errors still surface.

            suppressHydrationWarning here covers a third interference pattern:
            some extensions (observed: a popup blocker) rewrite this exact tag
            itself - e.g. adding their own `src` - before React can hydrate it,
            which React would otherwise report as a mismatch on this node. */}
        <script suppressHydrationWarning dangerouslySetInnerHTML={{ __html: EXTENSION_GUARD }} />
      </head>
      <body className="antialiased" suppressHydrationWarning>{children}</body>
    </html>
  );
}
