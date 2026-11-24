"""Key names, chord parsing, and Tk key event conversion (no Windows API calls)."""
import os

# Canonical text is stable across locales and stored in script JSON.
SPECIAL = {
    'SPACE':('Space',0x20), 'ENTER':('Enter',0x0d), 'TAB':('Tab',0x09), 'ESC':('Esc',0x1b),
    'SHIFT':('Shift',0x10), 'CTRL':('Ctrl',0x11), 'ALT':('Alt',0x12),
    'LEFT':('Left',0x25), 'UP':('Up',0x26), 'RIGHT':('Right',0x27), 'DOWN':('Down',0x28),
    'HOME':('Home',0x24), 'END':('End',0x23), 'PAGEUP':('PageUp',0x21), 'PAGEDOWN':('PageDown',0x22),
    'INSERT':('Insert',0x2d), 'DELETE':('Delete',0x2e), 'CAPSLOCK':('CapsLock',0x14),
    'NUMLOCK':('NumLock',0x90), 'SCROLLLOCK':('ScrollLock',0x91), 'PAUSE':('Pause',0x13),
    'PRINTSCREEN':('PrintScreen',0x2c), 'LWIN':('LWin',0x5b), 'RWIN':('RWin',0x5c),
    'NUMMULTIPLY':('NumMultiply',0x6a), 'NUMADD':('NumAdd',0x6b), 'NUMSUBTRACT':('NumSubtract',0x6d),
    'NUMDECIMAL':('NumDecimal',0x6e), 'NUMDIVIDE':('NumDivide',0x6f),
    'SEMICOLON':('Semicolon',0xba), 'EQUALS':('Equals',0xbb), 'COMMA':('Comma',0xbc),
    'MINUS':('Minus',0xbd), 'PERIOD':('Period',0xbe), 'SLASH':('Slash',0xbf),
    'BACKTICK':('Backtick',0xc0), 'LBRACKET':('LBracket',0xdb), 'BACKSLASH':('Backslash',0xdc),
    'RBRACKET':('RBracket',0xdd), 'QUOTE':('Quote',0xde), 'OEM102':('Oem102',0xe2),
}
for i in range(10):SPECIAL['NUMPAD'+str(i)]=('Numpad'+str(i),0x60+i)
ALIASES={'ESCAPE':'ESC','CONTROL':'CTRL','RETURN':'ENTER','PRIOR':'PAGEUP','NEXT':'PAGEDOWN'}
VK_TO_NAME={v:name for name,v in SPECIAL.values()}
EXTENDED_VKS={0x21,0x22,0x23,0x24,0x25,0x26,0x27,0x28,0x2d,0x2e,0x2c,0x5b,0x5c,0x6f,0x90}
RESERVED={0x08,0x75,0x76,0x77}

def parse_token(token):
    k=str(token).strip().upper();k=ALIASES.get(k,k)
    if k in SPECIAL:return SPECIAL[k]
    if len(k)==1 and ('A'<=k<='Z' or '0'<=k<='9'):return k,ord(k)
    if k.startswith('F') and k[1:].isdigit() and 1<=int(k[1:])<=24:
        n=int(k[1:]);return f'F{n}',0x70+n-1
    raise ValueError('Phím không được hỗ trợ: '+str(token))

def parse_chord(text):
    words=str(text).split()
    if not words:raise ValueError('Hãy bấm ít nhất một phím.')
    names=[];codes=[]
    for word in words:
        name,vk=parse_token(word)
        if vk in RESERVED:raise ValueError('Backspace, F6, F7 và F8 không được dùng làm thao tác.')
        if vk in codes:raise ValueError('Một tổ hợp không được có phím trùng nhau.')
        names.append(name);codes.append(vk)
    if len(codes)>32:raise ValueError('Một tổ hợp tối đa 32 phím.')
    return names,codes

def from_tk_event(event):
    """Return canonical name, or reserved edit/hotkey marker, or None.

    On Windows event.keycode is the actual Win32 virtual key and gives layout-
    independent physical keys even if Shift changes the generated character.
    """
    sym=str(getattr(event,'keysym','') or '')
    aliases={'BackSpace':'Backspace','Shift_L':'Shift','Shift_R':'Shift','Control_L':'Ctrl','Control_R':'Ctrl',
             'Alt_L':'Alt','Alt_R':'Alt','ISO_Level3_Shift':'Alt','Meta_L':'LWin','Meta_R':'RWin',
             'Super_L':'LWin','Super_R':'RWin','Return':'Enter','KP_Enter':'Enter','Escape':'Esc',
             'space':'Space','Prior':'PageUp','Next':'PageDown','Caps_Lock':'CapsLock','Num_Lock':'NumLock',
             'Scroll_Lock':'ScrollLock','Print':'PrintScreen','KP_Multiply':'NumMultiply','KP_Add':'NumAdd',
             'KP_Subtract':'NumSubtract','KP_Decimal':'NumDecimal','KP_Divide':'NumDivide',
             'semicolon':'Semicolon','equal':'Equals','comma':'Comma','minus':'Minus','period':'Period',
             'slash':'Slash','grave':'Backtick','bracketleft':'LBracket','backslash':'Backslash',
             'bracketright':'RBracket','apostrophe':'Quote'}
    if sym=='BackSpace':return 'Backspace'
    if sym in ('F6','F7','F8'):return sym
    vk=getattr(event,'keycode',None)
    if os.name=='nt' and isinstance(vk,int):
        if vk==0x08:return 'Backspace'
        if 0x70<=vk<=0x87:return 'F'+str(vk-0x70+1)
        if 0x30<=vk<=0x39 or 0x41<=vk<=0x5a:return chr(vk)
        if vk in VK_TO_NAME:return VK_TO_NAME[vk]
    if sym in aliases:return aliases[sym]
    if sym.startswith('KP_') and sym[3:].isdigit() and 0<=int(sym[3:])<=9:return 'Numpad'+sym[3:]
    try:return parse_token(sym)[0]
    except ValueError:return None
