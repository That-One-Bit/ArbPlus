# ArbPlus Tkinter Extension (Python)
# @arbplus-meta name="Tkinter"
# @arbplus-meta version="0.1"
# @arbplus-meta author="ThatOneBit"
# @arbplus-meta description="Python based extension bringing native Tkinter functions to ArbPlus."
# @arbplus-meta dependencies="tkinter, customtkinter"
# @arbplus-meta languages="python"
u='Supply String'
t=isinstance
s=ImportError
q='ced'
p='Input'
o='Open Files'
n='py'
m='val'
l=False
k=list
f='_max'
e='_min'
d='./'
c='*.*'
b='All Files'
X='question'
W='Default message.'
V='Default Title'
U='types'
T=hasattr
R='initial'
Q=True
N='highlight'
M='detail'
L='icon'
K='Display root not found.'
J=staticmethod
I=len
G=Exception
E='parent'
D=None
B=str
F=Q
Y=''
r=Q
v=''
try:import tkinter as w;from tkinter import filedialog as Z,messagebox as O,simpledialog as g,colorchooser as x;F=Q
except s as h:F=l;Y=B(h)
try:import customtkinter as z;r=Q
except s as h:r=l;v=B(h)
S=D
def H():
	global S,F,Y
	if not F:return
	try:
		if S is D or not S.winfo_exists():S=w.Tk();S.withdraw();S.attributes('-topmost',Q)
		return S
	except G as A:F=l;Y=B(A);return
def A(val):
	A=val
	if A is D:return''
	if T(A,m):return B(A.val)
	if T(A,n):return B(A.py())
	return B(A)
def i(raw_val):
	C=raw_val;E=[(b,c)]
	if not C:return E
	if T(C,n):C=C.py()
	elif T(C,m):C=C.val
	if t(C,B):
		C=C.strip()
		if C.startswith('[')and C.endswith(']')or C.startswith('(')and C.endswith(')'):
			try:C=ast.literal_eval(C)
			except G:return E
		else:return E
	try:
		F=[]
		for D in C:
			if T(D,n):D=D.py()
			elif T(D,m):D=D.val
			if t(D,(k,tuple))and I(D)>=2:H=A(D[0]);J=A(D[1]);F.append((H,J))
		return F if F else E
	except G:return E
def C(msg=''):return f"Error: tkinter not available — {Y}"if not msg else f"Error: {msg}"
class P:
	@J
	def showWarning(args,kwargs):
		N=args;J=kwargs
		if not F:return C()
		P=H()
		if P is D:return C(K)
		try:R=A(N[0])if N else'Warning';S=A(N[1])if I(N)>1 else'Default warning message.';T=A(J.get(L))if L in J else'warning';U=A(J.get(M))if M in J else D;V=A(J.get(E))if E in J else P;P.update();O.showwarning(B(R),B(S),icon=T,detail=U,parent=V);return Q
		except G as W:return C(B(W))
	@J
	def showError(args,kwargs):
		N=args;J=kwargs
		if not F:return C()
		P=H()
		if P is D:return C(K)
		try:R=A(N[0])if N else'Error';S=A(N[1])if I(N)>1 else'Default error message.';T=A(J.get(L))if L in J else'error';U=A(J.get(M))if M in J else D;V=A(J.get(E))if E in J else P;P.update();O.showerror(B(R),B(S),icon=T,detail=U,parent=V);return Q
		except G as W:return C(B(W))
	@J
	def showInfo(args,kwargs):
		N=args;J=kwargs
		if not F:return C()
		P=H()
		if P is D:return C(K)
		try:R=A(N[0])if N else'Information';S=A(N[1])if I(N)>1 else'Default information.';T=A(J.get(L))if L in J else'info';U=A(J.get(M))if M in J else D;V=A(J.get(E))if E in J else P;P.update();O.showinfo(B(R),B(S),icon=T,detail=U,parent=V);return Q
		except G as W:return C(B(W))
	@J
	def askyesno(args,kwargs):
		P=args;J=kwargs
		if not F:return C()
		Q=H()
		if Q is D:return C(K)
		try:R=A(P[0])if P else V;S=A(P[1])if I(P)>1 else W;T=A(J.get(L))if L in J else X;U=A(J.get(M))if M in J else D;Y=A(J.get(N))if N in J else D;Z=A(J.get(E))if E in J else Q;Q.update();return O.askyesno(B(R),B(S),default=Y,icon=T,detail=U,parent=Z)
		except G as a:return C(B(a))
	@J
	def askquestion(args,kwargs):
		P=args;J=kwargs
		if not F:return C()
		Q=H()
		if Q is D:return C(K)
		try:R=A(P[0])if P else V;S=A(P[1])if I(P)>1 else W;T=A(J.get(L))if L in J else X;U=A(J.get(M))if M in J else D;Y=A(J.get(N))if N in J else D;Z=A(J.get(E))if E in J else Q;Q.update();return O.askquestion(B(R),B(S),default=Y,icon=T,detail=U,parent=Z)
		except G as a:return C(B(a))
	@J
	def askokcancel(args,kwargs):
		P=args;J=kwargs
		if not F:return C()
		Q=H()
		if Q is D:return C(K)
		try:R=A(P[0])if P else V;S=A(P[1])if I(P)>1 else W;T=A(J.get(L))if L in J else X;U=A(J.get(M))if M in J else D;Y=A(J.get(N))if N in J else D;Z=A(J.get(E))if E in J else Q;Q.update();return O.askokcancel(B(R),B(S),default=Y,icon=T,detail=U,parent=Z)
		except G as a:return C(B(a))
	@J
	def askretrycancel(args,kwargs):
		P=args;J=kwargs
		if not F:return C()
		Q=H()
		if Q is D:return C(K)
		try:R=A(P[0])if P else V;S=A(P[1])if I(P)>1 else W;T=A(J.get(L))if L in J else X;U=A(J.get(M))if M in J else D;Y=A(J.get(N))if N in J else D;Z=A(J.get(E))if E in J else Q;Q.update();return O.askretrycancel(B(R),B(S),default=Y,icon=T,detail=U,parent=Z)
		except G as a:return C(B(a))
	@J
	def askyesnocancel(args,kwargs):
		P=args;J=kwargs
		if not F:return C()
		Q=H()
		if Q is D:return C(K)
		try:R=A(P[0])if P else V;S=A(P[1])if I(P)>1 else W;T=A(J.get(L))if L in J else X;U=A(J.get(M))if M in J else D;Y=A(J.get(N))if N in J else D;Z=A(J.get(E))if E in J else Q;Q.update();return O.askyesnocancel(B(R),B(S),default=Y,icon=T,detail=U,parent=Z)
		except G as a:return C(B(a))
class a:
	@J
	def askopenfilename(args,kwargs):
		L=kwargs;J=args
		if not F:return C()
		M=H()
		if M is D:return C(K)
		try:N=A(J[0])if J else'Open File';O=A(J[1])if I(J)>1 else d;P=i(L.get(U))if U in L else[(b,c)];Q=A(L.get(E))if E in L else M;M.update();return Z.askopenfilename(title=B(N),initialdir=O,filetypes=P,parent=Q)
		except G as R:return C(B(R))
	@J
	def askopenfilenames(args,kwargs):
		L=kwargs;J=args
		if not F:return C()
		M=H()
		if M is D:return C(K)
		try:N=A(J[0])if J else o;O=A(J[1])if I(J)>1 else d;P=i(L.get(U))if U in L else[(b,c)];Q=A(L.get(E))if E in L else M;M.update();return k(Z.askopenfilenames(title=B(N),initialdir=O,filetypes=P,parent=Q))
		except G as R:return C(B(R))
	@J
	def asksaveasfilename(args,kwargs):
		N='default';L=args;J=kwargs
		if not F:return C()
		M=H()
		if M is D:return C(K)
		try:O=A(L[0])if L else o;P=A(L[1])if I(L)>1 else d;Q=i(J.get(U))if U in J else[(b,c)];R=A(J.get(E))if E in J else M;S=A(J.get(N))if N in J else D;M.update();return Z.asksaveasfilename(title=B(O),initialdir=P,filetypes=Q,parent=R,defaultextension=S)
		except G as T:return C(B(T))
	@J
	def askdirectory(args,kwargs):
		N='mexist';L=kwargs;J=args
		if not F:return C()
		M=H()
		if M is D:return C(K)
		try:O=A(J[0])if J else o;P=A(J[1])if I(J)>1 else d;Q=A(L.get(N))if N in L else TRUE;R=A(L.get(E))if E in L else M;M.update();return k(Z.askdirectory(title=B(O),initialdir=P,mustexist=Q,parent=R))
		except G as S:return C(B(S))
class j:
	@J
	def askstring(args,kwargs):
		L=kwargs;J=args
		if not F:return C()
		M=H()
		if M is D:return C(K)
		try:
			O=A(J[0])if J else u;P=A(J[1])if I(J)>1 else p;Q=A(L.get(R))if R in L else D;S=A(L.get(E))if E in L else M;M.update();N=g.askstring(B(O),B(P),initialvalue=Q,parent=S)
			if N==D:return q
			else:return N
		except G as T:return C(B(T))
	@J
	def askinteger(args,kwargs):
		L=args;J=kwargs
		if not F:return C()
		M=H()
		if M is D:return C(K)
		try:
			O=A(L[0])if L else'Supply Integer';P=A(L[1])if I(L)>1 else p;Q=A(J.get(R))if R in J else D;S=A(J.get(E))if E in J else M;T=A(J.get(e))if e in J else D;U=A(J.get(f))if f in J else D;M.update();N=g.askinteger(B(O),B(P),minvalue=T,maxvalue=U,initialvalue=Q,parent=S)
			if N==D:return q
			else:return N
		except G as V:return C(B(V))
	@J
	def askfloat(args,kwargs):
		L=args;J=kwargs
		if not F:return C()
		M=H()
		if M is D:return C(K)
		try:
			O=A(L[0])if L else'Supply Float';P=A(L[1])if I(L)>1 else p;Q=A(J.get(R))if R in J else D;S=A(J.get(E))if E in J else M;T=A(J.get(e))if e in J else D;U=A(J.get(f))if f in J else D;M.update();N=g.askfloat(B(O),B(P),minvalue=T,maxvalue=U,initialvalue=Q,parent=S)
			if N==D:return q
			else:return N
		except G as V:return C(B(V))
class y:
	@J
	def color(args,kwargs):
		I=kwargs
		if not F:return C()
		J=H()
		if J is D:return C(K)
		try:L=A(args[0])if args else u;M=A(I.get(R))if R in I else D;N=A(I.get(E))if E in I else J;J.update();return x.askcolor(title=B(L),color=M,parent=N)[1]
		except G as O:return C(B(O))
def A0(engine):A=engine;A.register_extension('tk.show_info',P.showInfo);A.register_extension('tk.show_warn',P.showWarning);A.register_extension('tk.show_error',P.showError);A.register_extension('tk.ask_yn',P.askyesno);A.register_extension('tk.ask_qt',P.askquestion);A.register_extension('tk.ask_okc',P.askokcancel);A.register_extension('tk.ask_ryc',P.askretrycancel);A.register_extension('tk.ask_ync',P.askyesnocancel);A.register_extension('tk.file_open',a.askopenfilename);A.register_extension('tk.files_open',a.askopenfilenames);A.register_extension('tk.file_save',a.asksaveasfilename);A.register_extension('tk.dir_open',a.askdirectory);A.register_extension('tk.in_str',j.askstring);A.register_extension('tk.in_int',j.askinteger);A.register_extension('tk.in_flt',j.askfloat);A.register_extension('tk.color',y.color)