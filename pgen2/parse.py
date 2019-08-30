# Copyright 2004-2005 Elemental Security, Inc. All Rights Reserved.
# Licensed to PSF under a Contributor Agreement.

"""Parser engine for the grammar tables generated by pgen.

The grammar table must be loaded first.

See Parser/parser.c in the Python distribution for additional info on
how this parsing engine works.
"""

from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
  from _devbuild.gen.syntax_asdl import token
  from pgen2.grammar import Grammar


class ParseError(Exception):
    """Exception to signal the parser is stuck."""

    def __init__(self, msg, typ, opaque):
        # type: (str, int, token) -> None
        Exception.__init__(self, "%s: type=%r, opaque=%r" % (msg, typ, opaque))
        self.msg = msg
        self.type = typ
        self.opaque = opaque


class PNode(object):
  __slots__ = ('typ', 'tok', 'children')

  def __init__(self, typ, tok, children):
    # type: (int, token, List[PNode]) -> None
    self.typ = typ  # token or non-terminal
    self.tok = tok  # opaque object that is passed back to "convert" callback.
                    # In Oil, this is syntax_asdl.token.  In OPy, it's a
                    # 3-tuple (val, prefix, loc)
                    # NOTE: This is None for the first entry in the stack?
    self.children = children

  def __repr__(self):
    # type: () -> str
    tok_str = str(self.tok) if self.tok else '-'
    ch_str = 'with %d children' % len(self.children) \
        if self.children is not None else ''
    return '(PNode %s %s %s)' % (self.typ, tok_str, ch_str)


class Parser(object):
    """Parser engine.

    The proper usage sequence is:

    p = Parser(grammar, [converter])  # create instance
    p.setup([start])                  # prepare for parsing
    <for each input token>:
        if p.addtoken(...):           # parse a token; may raise ParseError
            break
    root = p.rootnode                 # root of abstract syntax tree

    A Parser instance may be reused by calling setup() repeatedly.

    A Parser instance contains state pertaining to the current token
    sequence, and should not be used concurrently by different threads
    to parse separate token sequences.

    See driver.py for how to get input tokens by tokenizing a file or
    string.

    Parsing is complete when addtoken() returns True; the root of the
    abstract syntax tree can then be retrieved from the rootnode
    instance variable.  When a syntax error occurs, addtoken() raises
    the ParseError exception.  There is no error recovery; the parser
    cannot be used after a syntax error was reported (but it can be
    reinitialized by calling setup()).
    """

    def __init__(self, grammar, convert=None):
        # type: (Grammar, Any) -> None
        """Constructor.

        The grammar argument is a grammar.Grammar instance; see the
        grammar module for more information.

        The parser is not ready yet for parsing; you must call the
        setup() method to get it started.

        The optional convert argument is a function mapping concrete
        syntax tree nodes to abstract syntax tree nodes.  If not
        given, no conversion is done and the syntax tree produced is
        the concrete syntax tree.  If given, it must be a function of
        two arguments, the first being the grammar (a grammar.Grammar
        instance), and the second being the concrete syntax tree node
        to be converted.  The syntax tree is converted from the bottom
        up.

        A concrete syntax tree node is a (type, value, context, nodes)
        tuple, where type is the node type (a token or symbol number),
        value is None for symbols and a string for tokens, context is
        None or an opaque value used for error reporting (typically a
        (lineno, offset) pair), and nodes is a list of children for
        symbols, and None for tokens.

        An abstract syntax tree node may be anything; this is entirely
        up to the converter function.
        """
        self.grammar = grammar
        self.convert = convert or (lambda grammar, node: node)

    def setup(self, start=None):
        # type: (int) -> None
        """Prepare for parsing.

        This *must* be called before starting to parse.

        The optional argument is an alternative start symbol; it
        defaults to the grammar's start symbol.

        You can use a Parser instance to parse any number of programs;
        each time you call setup() the parser is reset to an initial
        state determined by the (implicit or explicit) start symbol.
        """
        if start is None:
            start = self.grammar.start
        newnode = PNode(start, None, [])
        # Each stack entry is a tuple: (dfa, state, node).
        self.stack = [(self.grammar.dfas[start], 0, newnode)]
        self.rootnode = None

    def addtoken(self, typ, opaque, ilabel):
        # type: (int, token, int) -> bool
        """Add a token; return True iff this is the end of the program."""
        # Loop until the token is shifted; may raise exceptions

        # Andy NOTE: This is not linear time, i.e. a constant amount of work
        # for each token?  Is it O(n^2) as the ANTLR paper says?
        # Do the "accelerators" in pgen.c have anything to do with it?

        while True:
            dfa, state, node = self.stack[-1]
            states, _ = dfa
            arcs = states[state]
            # Look for a state with this label
            for ilab, newstate in arcs:
                t = self.grammar.labels[ilab]
                if ilabel == ilab:
                    # Look it up in the list of labels
                    assert t < 256, t
                    # Shift a token; we're done with it
                    self.shift(typ, opaque, newstate)
                    # Pop while we are in an accept-only state
                    state = newstate
                    while states[state] == [(0, state)]:
                        self.pop()
                        if not self.stack:
                            # Done parsing!
                            return True
                        dfa, state, node = self.stack[-1]
                        states, _ = dfa
                    # Done with this token
                    return False
                elif t >= 256:
                    # See if it's a symbol and if we're in its first set
                    itsdfa = self.grammar.dfas[t]
                    itsstates, itsfirst = itsdfa
                    if ilabel in itsfirst:
                        # Push a symbol
                        self.push(t, opaque, self.grammar.dfas[t], newstate)
                        break # To continue the outer while loop

            else:  # note: for/else not supported in C++
                if (0, state) in arcs:
                    # An accepting state, pop it and try something else
                    self.pop()
                    if not self.stack:
                        # Done parsing, but another token is input
                        raise ParseError("too much input", typ, opaque)
                else:
                    # No success finding a transition
                    raise ParseError("bad input", typ, opaque)

    def shift(self, typ, opaque, newstate):
        # type: (int, token, int) -> None
        """Shift a token.  (Internal)"""
        dfa, _, node = self.stack[-1]
        newnode = PNode(typ, opaque, None)
        newnode = self.convert(self.grammar, newnode)
        if newnode is not None:
            node.children.append(newnode)
        self.stack[-1] = (dfa, newstate, node)

    def push(self, typ, opaque, newdfa, newstate):
        # type: (int, token, Any, int) -> None
        """Push a nonterminal.  (Internal)"""
        dfa, _, node = self.stack[-1]
        newnode = PNode(typ, opaque, [])
        self.stack[-1] = (dfa, newstate, node)
        self.stack.append((newdfa, 0, newnode))

    def pop(self):
        # type: () -> None
        """Pop a nonterminal.  (Internal)"""
        _, _, popnode = self.stack.pop()
        newnode = self.convert(self.grammar, popnode)
        if newnode is not None:
            if self.stack:
                _, _, node = self.stack[-1]
                node.children.append(newnode)
            else:
                self.rootnode = newnode
