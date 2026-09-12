% =========================================================================
%  hmcnote.cls -- Sorin's HMC class notes
%
%  Usage:
%      \documentclass[dark]{hmcnote}     % Tokyo Night on screen
%      \documentclass[light]{hmcnote}    % same palette, white page, for print
%
%  Other options:
%      12pt, 11pt, 10pt   base size (default 11pt)
%      twocolumn, landscape, ...  passed through to article
%
%  Compile with LuaLaTeX (preferred -- gets Inter + Fira Math, which is what
%  makes it look like Obsidian). pdfLaTeX also works and falls back to
%  Latin Modern automatically.
% =========================================================================

\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{hmcnote}[2026/09/12 v1.0 HMC class notes, Tokyo Night]

% ---- options ------------------------------------------------------------
\newif\ifhmc@dark
\DeclareOption{dark}{\hmc@darktrue}
\DeclareOption{light}{\hmc@darkfalse}
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ExecuteOptions{light}
\ProcessOptions\relax

\LoadClass[11pt]{article}

% ---- core packages ------------------------------------------------------
\RequirePackage{iftex}
\RequirePackage{etoolbox}
\RequirePackage[dvipsnames,svgnames,table]{xcolor}
\RequirePackage{amsmath,amssymb,amsthm}
\RequirePackage{mathtools}
\RequirePackage{graphicx}
\RequirePackage{geometry}
\RequirePackage{microtype}
\RequirePackage{enumitem}
\RequirePackage{booktabs}
\RequirePackage{array}
\RequirePackage{longtable}
\RequirePackage{cancel}
\RequirePackage{tcolorbox}
\RequirePackage{titlesec}
\RequirePackage{fancyhdr}
\RequirePackage{siunitx}
\RequirePackage{caption}
\tcbuselibrary{skins,breakable}

\geometry{
  letterpaper,
  top=2.4cm, bottom=2.4cm, left=2.6cm, right=2.6cm,
  headsep=0.6cm, footskip=1.1cm
}

% =========================================================================
%  Tokyo Night palette
%  Lifted from the Obsidian theme so the PDF matches what's on screen.
% =========================================================================
\definecolor{tnbg}       {HTML}{1A1B26}  % editor background
\definecolor{tnbgalt}    {HTML}{16161E}  % darker panel
\definecolor{tnbghigh}   {HTML}{292E42}  % highlighted line / box fill
\definecolor{tnfg}       {HTML}{C0CAF5}  % body text
\definecolor{tnfgdim}    {HTML}{A9B1D6}  % secondary text
\definecolor{tncomment}  {HTML}{565F89}  % muted / comments / rules
\definecolor{tnblue}     {HTML}{7AA2F7}
\definecolor{tncyan}     {HTML}{7DCFFF}
\definecolor{tngreen}    {HTML}{9ECE6A}
\definecolor{tnpurple}   {HTML}{BB9AF7}
\definecolor{tnorange}   {HTML}{FF9E64}
\definecolor{tnred}      {HTML}{F7768E}
\definecolor{tnyellow}   {HTML}{E0AF68}
\definecolor{tnteal}     {HTML}{1ABC9C}
\definecolor{tnaccent}   {HTML}{AA62D0}  % your Obsidian accent colour

% ---- semantic roles, remapped per mode ----------------------------------
% Everything downstream refers to these, never to the raw palette, so the
% dark/light switch is a single block.
\ifhmc@dark
  \colorlet{PageBG}      {tnbg}
  \colorlet{BodyText}    {tnfg}
  \colorlet{DimText}     {tnfgdim}
  \colorlet{Muted}       {tncomment}
  \colorlet{Rule}        {tncomment}
  \colorlet{BoxFill}     {tnbghigh}
  \colorlet{CodeFill}    {tnbgalt}
  \colorlet{Heading}     {tnaccent}
  \colorlet{SubHeading}  {tnpurple}
  \colorlet{LinkColor}   {tncyan}
  \colorlet{MathColor}   {tnfg}
\else
  \definecolor{paperwhite}{HTML}{FDFDFE}
  \definecolor{inkdark}   {HTML}{1F2233}
  \definecolor{inkdim}    {HTML}{4A5170}
  % Slightly deepened accents: the on-screen colours are tuned for a dark
  % ground and wash out badly on white.
  \definecolor{tnblued}   {HTML}{3A62C4}
  \definecolor{tnpurpled} {HTML}{7C4DBE}
  \definecolor{tnaccentd} {HTML}{8A3FB5}
  \definecolor{tnteald}   {HTML}{127D68}
  \colorlet{PageBG}      {paperwhite}
  \colorlet{BodyText}    {inkdark}
  \colorlet{DimText}     {inkdim}
  \colorlet{Muted}       {inkdim}
  \colorlet{Rule}        {tncomment!40}
  \colorlet{BoxFill}     {tnpurpled!6}
  \colorlet{CodeFill}    {tncomment!10}
  \colorlet{Heading}     {tnaccentd}
  \colorlet{SubHeading}  {tnpurpled}
  \colorlet{LinkColor}   {tnblued}
  \colorlet{MathColor}   {inkdark}
\fi

\pagecolor{PageBG}
% Set at begin-document so it survives into the body; maths inherits this, so
% no \everymath / \everydisplay hackery is needed (and those break amsmath's
% align, which is built on \halign inside $$).
\AtBeginDocument{\color{BodyText}}

% =========================================================================
%  Fonts
%  LuaLaTeX/XeLaTeX: Inter for text, Fira Math for maths -- close to the
%  sans-ish look Obsidian gives you. pdfLaTeX: Latin Modern fallback.
% =========================================================================
\ifPDFTeX
  \RequirePackage[T1]{fontenc}
  \RequirePackage[utf8]{inputenc}
  \RequirePackage{lmodern}
  \renewcommand{\familydefault}{\sfdefault}
\else
  \RequirePackage{fontspec}
  \RequirePackage{unicode-math}
  \IfFontExistsTF{Inter-Regular.otf}{
    \setsansfont{Inter}[
      Extension      = .otf,
      UprightFont    = *-Regular,
      BoldFont       = *-Bold,
      ItalicFont     = *-Italic,
      BoldItalicFont = *-BoldItalic,
      Scale          = 0.96,
    ]
    \setmainfont{Inter}[
      Extension      = .otf,
      UprightFont    = *-Regular,
      BoldFont       = *-Bold,
      ItalicFont     = *-Italic,
      BoldItalicFont = *-BoldItalic,
      Scale          = 0.96,
    ]
  }{}
  \IfFontExistsTF{FiraMono-Regular.otf}{
    \setmonofont{FiraMono}[
      Extension   = .otf,
      UprightFont = *-Regular,
      BoldFont    = *-Bold,
      Scale       = 0.90,
    ]
  }{}
  \IfFontExistsTF{FiraMath-Regular.otf}{
    \setmathfont{FiraMath-Regular.otf}
  }{}
\fi

% =========================================================================
%  Headings
% =========================================================================
\titleformat{\section}
  {\normalfont\Large\bfseries\color{Heading}}
  {\thesection}{0.8em}{}
  [{\vspace{2pt}\color{Rule}\titlerule[0.7pt]}]
\titleformat{\subsection}
  {\normalfont\large\bfseries\color{SubHeading}}
  {\thesubsection}{0.7em}{}
\titleformat{\subsubsection}
  {\normalfont\normalsize\bfseries\color{SubHeading!85}}
  {\thesubsubsection}{0.6em}{}

\titlespacing*{\section}      {0pt}{1.6em plus .3em minus .2em}{0.7em}
\titlespacing*{\subsection}   {0pt}{1.2em plus .2em minus .2em}{0.5em}
\titlespacing*{\subsubsection}{0pt}{1.0em plus .2em minus .2em}{0.4em}

% =========================================================================
%  Links
% =========================================================================
\RequirePackage{hyperref}
\hypersetup{
  colorlinks = true,
  linkcolor  = LinkColor,
  urlcolor   = LinkColor,
  citecolor  = LinkColor,
  pdfborder  = {0 0 0},
}

% =========================================================================
%  Header / footer
% =========================================================================
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\footrulewidth}{0pt}
\patchcmd{\headrule}{\hrule}{\color{Rule}\hrule}{}{}
\fancyhead[L]{\small\color{Muted}\hmc@course}
\fancyhead[R]{\small\color{Muted}\hmc@notetitle}
\fancyfoot[C]{\small\color{Muted}\thepage}

% First page carries the full title block, so the running head would just say
% the same thing twice. Footer only.
\fancypagestyle{hmcfirst}{%
  \fancyhf{}%
  \renewcommand{\headrulewidth}{0pt}%
  \fancyfoot[C]{\small\color{Muted}\thepage}%
}

% =========================================================================
%  Title block
%
%  \course{Phys 116 -- Quantum Mechanics}
%  \lecture{4}{Stern--Gerlach}{2026-01-21}
% =========================================================================
\def\hmc@course{}
\def\hmc@notetitle{}
\newcommand{\course}[1]{\def\hmc@course{#1}}

\newcommand{\lecture}[3]{%
  \def\hmc@notetitle{#2}%
  \thispagestyle{hmcfirst}%
  \begingroup
    \noindent
    {\color{Muted}\small\scshape \hmc@course \ifx\hmc@course\@empty\else\ \textbullet\ \fi Lecture #1 \hfill #3}\par
    \vspace{0.35em}
    {\color{Rule}\rule{\linewidth}{0.9pt}}\par
    \vspace{0.55em}
    {\color{Heading}\LARGE\bfseries #2}\par
    \vspace{0.9em}
  \endgroup
}

% =========================================================================
%  Theorem-like environments
%  tcolorbox versions so they read as cards, like Obsidian callouts.
% =========================================================================
\newtcolorbox{hmc@callout}[2][]{
  enhanced, breakable,
  colback     = BoxFill,
  colframe    = #2,
  coltitle    = PageBG,
  colbacktitle= #2,
  boxrule     = 0pt,
  leftrule    = 2.5pt,
  arc         = 2pt,
  left        = 8pt, right = 8pt, top = 6pt, bottom = 6pt,
  fonttitle   = \bfseries\small,
  #1
}

\newenvironment{callout}[2][Note]
  {\begin{hmc@callout}[title={#1}]{#2}}
  {\end{hmc@callout}}

% Named shorthands matching Obsidian's callout types
\newenvironment{note}[1][Note]     {\begin{hmc@callout}[title={#1}]{tnblue}}  {\end{hmc@callout}}
\newenvironment{tip}[1][Tip]       {\begin{hmc@callout}[title={#1}]{tnteal}}  {\end{hmc@callout}}
\newenvironment{warning}[1][Warning]{\begin{hmc@callout}[title={#1}]{tnorange}}{\end{hmc@callout}}
\newenvironment{important}[1][Important]{\begin{hmc@callout}[title={#1}]{tnred}}{\end{hmc@callout}}
\newenvironment{example}[1][Example]{\begin{hmc@callout}[title={#1}]{tnpurple}}{\end{hmc@callout}}

% ---- classical amsthm environments, tinted to match --------------------
\newtheoremstyle{hmc}
  {0.8em}{0.8em}                  % above / below
  {}                              % body font
  {0pt}                           % indent
  {\bfseries\color{SubHeading}}   % head font
  {.}                             % punctuation
  {0.5em}                         % space after head
  {}
\theoremstyle{hmc}
\newtheorem{theorem}{Theorem}[section]
\newtheorem{lemma}[theorem]{Lemma}
\newtheorem{corollary}[theorem]{Corollary}
\newtheorem{proposition}[theorem]{Proposition}
\newtheorem{definition}[theorem]{Definition}
\newtheorem{remark}[theorem]{Remark}

\renewenvironment{proof}[1][\proofname]{%
  \par\pushQED{\qed}\normalfont\topsep6\p@\@plus6\p@\relax
  \trivlist\item[\hskip\labelsep\itshape\color{Muted}#1\@addpunct{.}]\ignorespaces
}{\popQED\endtrivlist\@endpefalse}

% =========================================================================
%  Code
% =========================================================================
% fvextra, not bare fancyvrb: md2tex emits Verbatim[breaklines=true] so long
% code lines wrap instead of running off the page, and only fvextra has it.
\RequirePackage{fvextra}
\newtcolorbox{codebox}[1][]{
  enhanced, breakable,
  colback  = CodeFill,
  colframe = Rule,
  boxrule  = 0.4pt,
  arc      = 2pt,
  left     = 6pt, right = 6pt, top = 4pt, bottom = 4pt,
  #1
}
\newcommand{\code}[1]{{\ttfamily\color{tngreen!80!BodyText}#1}}

% =========================================================================
%  Tables -- readable on a dark ground
% =========================================================================
\renewcommand{\arraystretch}{1.25}
\arrayrulecolor{Rule}
\newcommand{\hmctablehead}[1]{{\bfseries\color{SubHeading}#1}}

% =========================================================================
%  Captions
% =========================================================================
\captionsetup{
  font       = small,
  labelfont  = {bf,color=SubHeading},
  textfont   = {color=DimText},
  margin     = 1.2em,
}

% =========================================================================
%  Misc
% =========================================================================
\setlist{itemsep=0.15em, topsep=0.35em, parsep=0pt}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.55em}

% Images live next to the notes, in an images/ subfolder, exactly as Obsidian
% saves them. This lets \includegraphics{Pasted image 2026...} just work.
\graphicspath{{images/}{./}{../images/}}

% Obsidian-style embed: \embed{Pasted image 20260121111713.png}
% Oversized images are clamped so a screenshot never overflows the page.
\newcommand{\embed}[2][0.8\linewidth]{%
  \begin{center}%
    \includegraphics[width=#1,height=0.8\textheight,keepaspectratio]{\detokenize{#2}}%
  \end{center}%
}

% =========================================================================
%  Markdown support
%  Used by build/md2tex.py so the converter never has to load packages that
%  might clash with the engine in use.
% =========================================================================
\RequirePackage[normalem]{ulem}
\newcommand{\mdstrike}[1]{\sout{#1}}

\ifLuaTeX
  % lua-ul highlights correctly under unicode-math; soul does not.
  \RequirePackage{luacolor}
  \RequirePackage{lua-ul}
  \newcommand{\mdhl}[1]{\highLight[tnyellow!30]{#1}}
\else
  \newcommand{\mdhl}[1]{\textcolor{tnyellow}{#1}}
\fi

\endinput
