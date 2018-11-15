from os import system

def Gnuplot(scriptName, argsDict=None):
    gnuplotCommand = 'gnuplot'
    if argsDict:
        gnuplotCommand += ' -e "'
        for arg in argsDict.items():
            gnuplotCommand += arg[0] + '='
            if isinstance(arg[1], str):
                gnuplotCommand += '\'' + arg[1] + '\''
            elif isinstance(arg[1], bool):
                if arg[1] is True:
                    gnuplotCommand += '1'
                else:
                    gnuplotCommand += '0'
            else:
                gnuplotCommand += str(arg[1])
            gnuplotCommand += '; '
        gnuplotCommand  = gnuplotCommand[:-1]
        gnuplotCommand += '"'
    gnuplotCommand += ' ' + scriptName
    system(gnuplotCommand)
    return gnuplotCommand

