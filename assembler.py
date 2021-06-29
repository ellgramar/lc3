""" Assembler for teaching processor LC3 (original version)
    Tools exist to do same job, but check how much effort it
    is to do in Python. Order of BRanch flags relaxed, BR without
    flags interpreted as BRnzv (allways).

    With verbosity on prints source instructions without label
    replacements (immediates and registers in place) to stdout.
"""

from __future__ import print_function
from array import array
import os
import sys

try:
    input = raw_input
except:
    pass

reg_pos = [9, 6, 0]
flags = {'n': 1 << 11, 'z': 1 << 10, 'p': 1 << 9}
memory = array('H', [0] * (1 << 16))

swap = True       # need to swap bytes

instruction_info = dict((
    ('ADD', 0b1 << 12),
    ('AND', 0b0101 << 12),
    ('BR', 0b0),
    ('GETC', (0b1111 << 12) + 0x20),
    ('HALT', (0b1111 << 12) + 0x25),
    ('IN', (0b1111 << 12) + 0x23),
    ('JMP', 0b1100 << 12),
    ('JMPT', (0b1100000 << 9) + 1),
    ('JSR', 0b01001 << 11),
    ('JSRR', 0b010000 << 9),
    ('LD', 0b0010 << 12),
    ('LDI', 0b1010 << 12),
    ('LDR', 0b0110 << 12),
    ('LEA', 0b1110 << 12),
    ('NOT', (0b1001 << 12) + 0b111111),
    ('OUT', (0b1111 << 12) + 0x21),
    ('PUTS', (0b1111 << 12) + 0x22),
    ('PUTSP', (0b1111 << 12) + 0x24),
    ('RET', 0b1100000111000000),
    ('RTI', 0b1000 << 12),
    ('RTT', 0b1100000111000001),
    ('ST', 0b0011 << 12),
    ('STI', 0b1011 << 12),
    ('STR', 0b0111 << 12),
    ('TRAP', 0b1111 << 12),
    ))

immediate = dict((
    ('ADD', 5),
    ('AND', 5),
    ('BR', 9),
    ('GETC', 0),
    ('HALT', 0),
    ('IN', 0),
    ('JMP', 0),
    ('JMPT', 0),
    ('JSR', 11),
    ('JSRR', 0),
    ('LD', 9),
    ('LDI', 9),
    ('LDR', 6),
    ('LEA', 9),
    ('NOT', 9),
    ('OUT', 0),
    ('PUTS', 0),
    ('PUTSP', 0),
    ('RET', 0),
    ('RTI', 0),
    ('RTT', 0),
    ('ST', 9),
    ('STI', 9),
    ('STR', 6),
    ('TRAP', 8),
    ('UNDEFINED', 0)
    ))

immediate_mask = dict()
for im in immediate:
    immediate_mask[im] = (1 << immediate[im]) - 1

instructions = instruction_info.keys()


regs = dict(('R%1i' % r, r) for r in range(8))
labels = dict()
label_location = dict()


def put_and_show(n):
    if n < 0: n = (1<<16) + n
    memory[pc] = n
    if verbose:
        print(get_mem_str(pc), end='')


def get_mem_str(loc):
    return 'x{0:04X}: {1:016b} {1:04x} '.format(loc, memory[loc])


def reg(s, n=1):
    return registers[s.rstrip(', ')] << reg_pos[n]


def undefined(data):
    raise ValueError('Undefined Instruction')


def valid_label(word):
    if word[0] == 'x' and word[1].isdigit():
        return False
    return (word[0].isalpha() and
            all(c.isalpha() or c.isdigit() or c == '_' for c in word))


def get_immediate(word, mask=0xFFFF):
    if (word.startswith('x') and
        all(n in '-0123456789abcdefgABCDEF' for n in word[1:]) and
        not '-' in word[2:]
        ):
        return int('0' + word, 0) & mask
    elif word.startswith('#'):
        return int(word[1:]) & mask
    else:
        try:
            return int(word) & mask
        except ValueError:
            return


def process_instruction(words):
    """ Process ready split words from line and parse the line
        use put_and_show to show the instruction line without
        label values

    """
    global orig, pc
    found = ''
    if not words or words[0].startswith(';'):
        if verbose:
            print(3 * '\t', end='')
        return
    elif '.FILL' in words:
        word = words[words.index('.FILL') + 1]
        try:
            put_and_show(int(word))
        except ValueError:
            value = get_immediate(word)
            if value is None:
                if word in label_location:
                    label_location[word].append([pc, 0xFFFF, 16])
                else:
                    label_location[word] = [[pc, 0xFFFF, 16]]
            else:
                memory[pc] = value

        if words[0] != '.FILL':
            labels[words[0]] = pc
        pc += 1
        return    
    elif '.ORIG' in words:
        orig = pc = int('0' + words[1]
                        if words[1].startswith('x')
                        else words[1], 0)
        if verbose:
            print(3 * '\t', end='')
        return
    elif '.STRINGZ' in words:
        if valid_label(words[0]):
            labels[words[0]] = pc
        else:
            print('Warning: no label for .STRINGZ in line for PC = x%04x:\n%s' % (pc, line))
        s = line.split('"')
        string1 = string = s[1]
        # rejoin if "  inside quotes
        for st in s[2:]:
            if string.endswith('\\'):
                string += '"' + st

        # encode backslash to get special characters
        backslash = False
        for c in string:
            if not backslash:
                if c == '\\':
                    if not backslash:
                        backslash = True
                        continue
                m = ord(c)
            else:
                if c in 'nblr':
                    m = ord(c) - 100
                else:
                # easiest to implement:
                # anything else escaped is itself (unlike Python)
                    m = ord(c)

                backslash = False

            put_and_show(m)
            if verbose:
                print(repr(chr(m)))
            pc += 1
        put_and_show(0)
        pc += 1
        return
    elif '.BLKW' in words:
        labels[words[0]] = pc
        value = get_immediate(words[-1])
        if value is None or value <= 0:
            raise ValueError('Bad .BLKW immediate: %s, %r' %
                              (words[-1], value))
        pc += value
        return

    ind = -1
    if words[0].startswith('BR'):
        ind = 0
    elif words[1:] and words[1].startswith('BR'):
        ind = 1
    if ind >= 0 and len(words[ind]) <= 5:
        if all(c in flags for c in words[ind][2:].lower()):
            fl = 0
            # BR alone does not make sense so default to Branch always
            if words[ind] == 'BR':
                words[ind] = 'BRnzp'
            for f in words[ind][2:].lower():
                fl |= flags[f]
            words[ind] = 'BR'

    if words[0] in instructions:
        found = words[0]
    else:
        if valid_label(words[0]):
            labels[words[0]] = pc
        else:
            print('Warning: invalid label %s in line\n%s' % (words[0], line))

        if len(words) < 2:
            return
        found = words[1] if words[1] in instructions else ''

    if not found:
        word = words[0]
        if len(words) > 1:
            input('Not instruction:%s' % line)
            return
        else:
            if valid_label(word):
                if word in label_location:
                    label_location[word].append([pc, 0xFFFF, 16])
                else:
                    label_location[word] = [[pc, 0xFFFF, 16]]
            else:
                raise ValueError('Invalid label: %r, line:\n%s\n' %
                                    (word, line))
        return

    try:
        instruction = instruction_info[found]
    except KeyError:
        input('Unknown: %s' % found)
    else:
        if found == 'BR':
            instruction |= fl
        r = rc = 0
        rc += found == 'JMPT'
    
        for word in words[1:]:
            word = word.rstrip(',')
            if word in regs:
                t = regs[word] << reg_pos[rc]
                r |= t
                rc += 1
            else:
                value = get_immediate(word, immediate_mask[found])
                if value is not None:
                    instruction |= value
                    if found in ('ADD', 'AND'):
                        instruction |= 1 << 5
                elif word != found:
                    if valid_label(word):
                        if word in label_location:
                            label_location[word].append([pc, immediate_mask[found], immediate[found]])
                        else:
                            label_location[word] = [[pc, immediate_mask[found], immediate[found]]]
                    else:
                        raise ValueError('Invalid label: %r, line:\n%s\n' %
                                     (word, line))

            instruction |= r
            if found == 'JMPT':
                break

        put_and_show(instruction)
        pc += 1

def lc_hex(h):
    """ lc hex has not the first 0 """
    return hex(h)[1:]

def in_range(n, bits):
    return -(1<< (bits-1)) <=  n < (1<< (bits-1))
   
if __name__ == '__main__':

    code = r'''
        .ORIG   x3000
        NOT     R1, R1
        JSR     F      ; Jump to subroutine F.
        STI     R1, FN
        HALT
    FN  .FILL   3121 ; Address where fn will be stored.
    N   .FILL   3120 ; Address where n is located
    HELLO .STRINGZ  "N is too far!\n"

    ; Subroutine F begins
    F   AND     R1, R1, N ; Clear R1
        ADD     R1, R0, #-16
        STR     R6, R1, #3 ; problem test
        ADD     R1, R1, R1 ; R1 is R1 + R1
        ADD     R1, R1, x3 ; R1 is R1 + 3
        LD      R2, HELLO
        BRnz     F
        RET ; Return from subroutine
        .END'''

    fn = 'Nothing'
    while (fn and not os.path.exists(fn)):
        print('\n'.join(fn for fn in os.listdir(os.curdir)
                            if fn.endswith('.asm')))
        fn = input('''
    Give name of code file
    or empty for  test code: ''')  # .rstrip()
    # rstrip for Python3.2 CMD bug, Python3.2.1rc fixed

    if fn:
        with open(fn) as codefile:
            code = codefile.read()
        base = fn.rsplit('.', 1)[0] + '_py'
    else:
        print('Using test code')
        base = 'out'

    verbose = input('Verbose Y/n? ').lower() != 'n'

    # processing the lines
    for line in code.splitlines():
        # remove comments
        orig_line, line = line, line.split(';')[0]
        # add space after comma to make sure registers are space separated also (not with strings)
        if '"' not in line:
            line = line.replace(',', ', ')
        # drop comments
        words = (line.split()) if ';' in line else line.split()
        if '.END' in words:
                break
        process_instruction(words)
        if verbose:
            # show binary form without label values in verbose mode
            print('\t', orig_line)

    # producing output
    for label, value in label_location.items():
        if label not in labels:
            print('Bad label failure:')
            print(label, ':', label_location[label])
        else:
            for ref, mask, bits in value:
                current = labels[label] - ref - 1
                # gludge for absolute addresses,
                # but seems correct for some code (lc3os.asm)
                if memory[ref] == 0: # not instruction -> absolute
                    memory[ref] = labels[label]
                elif not in_range(current,bits) :
                    raise ValueError(("%s, mask %s, offset %s,  %s, ref %s" %
                            (label,
                            bin(mask),
                            labels[label] - ref,
                            bin(labels[label]),
                            hex(ref))))
                else:
                    memory[ref] |= mask & current

    # choose base different from standard utilities to enable comparison

    # symbol list for Simulators
    with open(base + '.sym', 'w') as f:
        print('''//Symbol Name		Page Address
//----------------	------------
//''', end='\t', file=f)

        print('\n//\t'.join('\t%-20s%4x' % (name, value)
                        for name, value in labels.items()), file=f)

    print(80 * '-', '\n')
    print('Symbol cross reference:'.center(60) +
            '\n\n\t%-20s%-10s%s' % ('NAME', 'PLACE', 'USED'),
            end='\n' + 80 * '-' + '\n\t')
    # some cutting required to drop 0 from hex numbers
    print('\n\n\t'.join('%-20s%-10s%s' %
           (key, lc_hex(item),
            ', '.join(map(lc_hex, (list(zip(*label_location[key]))[0]
                        if key in label_location else ''))))
          # sort case insensitively by key
          for key, item in sorted(labels.items(), key=lambda x: x[0].lower())))

    # binary numbers output
    print('\n.bin file saved as ', end='')

    with open(base + '.bin', 'w') as f:
        print(f.name)
        print('{0:016b}'.format(orig), file=f)  # orig address
        print('\n'.join('{0:016b}'.format(memory[m]) for m in range(orig, pc)),
                file=f)

    # object file for running in Simulator
    with open(base + '.obj', 'wb') as f:
        print('.obj file saved as', f.name)
        #do slice from right after code and write
        #(byteorder of 0 does not matter)
        memory[pc] = orig
        if swap:
            memory.byteswap()

        memory[pc:pc+1].tofile(f)
        memory[orig:pc].tofile(f)
        # better to restore swap for future, even program stops here
        if swap:
            memory.byteswap()