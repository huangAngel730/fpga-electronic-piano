# Read-only command/option discovery; no project, build or hardware access.
puts "REPORT_COMMANDS [info commands *report*]"
puts "TIMING_COMMANDS [info commands *tim*]"
foreach command {{report_timing -h} {report_timing -help} {set_option -h} {run -h}} {
    puts "QUERY $command"
    catch {eval $command} message
    puts $message
}
exit
