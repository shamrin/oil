#!/usr/bin/env bash

#### Lazy Evaluation of Alternative
i=0
x=x
echo ${x:-$((i++))}
echo $i
echo ${undefined:-$((i++))}
echo $i  # i is one because the alternative was only evaluated once
## status: 0
## stdout-json: "x\n0\n0\n1\n"
## N-I dash status: 2
## N-I dash stdout-json: "x\n0\n"

#### Default value when empty
empty=''
echo ${empty:-is empty}
## stdout: is empty

#### Default value when unset
echo ${unset-is unset}
## stdout: is unset

#### Unquoted with array as default value
set -- '1 2' '3 4'
argv.py X${unset=x"$@"x}X
argv.py X${unset=x$@x}X  # If you want OSH to split, write this
# osh
## STDOUT:
['Xx1', '2', '3', '4xX']
['Xx1', '2', '3', '4xX']
## END
## OK osh STDOUT:
['Xx1 2', '3 4xX']
['Xx1', '2', '3', '4xX']
## END

#### Quoted with array as default value
set -- '1 2' '3 4'
argv.py "X${unset=x"$@"x}X"
argv.py "X${unset=x$@x}X"  # OSH is the same here
## STDOUT:
['Xx1 2 3 4xX']
['Xx1 2 3 4xX']
## END
## BUG bash STDOUT:
['Xx1', '2', '3', '4xX']
['Xx1 2 3 4xX']
## END
## OK osh STDOUT:
['Xx1 2', '3 4xX']
['Xx1 2 3 4xX']
## END

#### Assign default with array
set -- '1 2' '3 4'
argv.py X${unset=x"$@"x}X
argv.py "$unset"
## STDOUT:
['Xx1', '2', '3', '4xX']
['x1 2 3 4x']
## END
## OK osh STDOUT:
['Xx1 2', '3 4xX']
['x1 2 3 4x']
## END

#### Assign default value when empty
empty=''
${empty:=is empty}
echo $empty
## stdout: is empty

#### Assign default value when unset
${unset=is unset}
echo $unset
## stdout: is unset

#### Alternative value when empty
v=foo
empty=''
echo ${v:+v is not empty} ${empty:+is not empty}
## stdout: v is not empty

#### Alternative value when unset
v=foo
echo ${v+v is not unset} ${unset:+is not unset}
## stdout: v is not unset

#### Error when empty
empty=''
echo ${empty:?'is em'pty}  # test eval of error
echo should not get here
## stdout-json: ""
## status: 1
## OK dash status: 2

#### Error when unset
echo ${unset?is empty}
echo should not get here
## stdout-json: ""
## status: 1
## OK dash status: 2

#### Error when unset
v=foo
echo ${v+v is not unset} ${unset:+is not unset}
## stdout: v is not unset
