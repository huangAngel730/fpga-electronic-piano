puts "READ_ONLY_TCL_QUERY"
puts [info commands *tim*]
puts [info commands *run*]
if {[llength [info commands help]] > 0} {
    help run
}
exit
