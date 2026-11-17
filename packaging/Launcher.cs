using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
class Launcher {
 [STAThread] static int Main(string[] args) {
  try {
   string root=AppDomain.CurrentDomain.BaseDirectory;
   string python=Path.Combine(root,"runtime",args.Length>0?"python.exe":"pythonw.exe");
   string script=Path.Combine(root,"app","main.py");
   string arguments="\""+script+"\"";
   foreach(string arg in args)arguments+=" \""+arg.Replace("\"","\\\"")+"\"";
   var start=new ProcessStartInfo(python,arguments){WorkingDirectory=root,UseShellExecute=false,CreateNoWindow=true};
   start.EnvironmentVariables.Remove("PYTHONHOME");start.EnvironmentVariables.Remove("PYTHONPATH");
   var p=Process.Start(start);p.WaitForExit();return p.ExitCode;
  } catch(Exception ex){MessageBox.Show(ex.Message,"ZOE2 Randomiser Beta");return 1;}
 }
}
