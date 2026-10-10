# Read-only command discovery. Does not open, modify, or build any project.
puts [info commands]
foreach command {{set_option -h} {run -h} {create_project -h} {set_device -h}} {
    puts "QUERY $command"
    catch {eval $command} message
    puts $message
}
exit
