import java.io.BufferedReader;
import java.io.InputStreamReader;
import org.m3.score.Protocol;

/** New desktop host, not Android callback/UI evidence. Public API only. */
public final class NightClient {
    public static void main(String[] args) throws Exception {
        Protocol.Session session = new Protocol.Session(new Protocol.Sink() {
            public void send(byte[] bytes) { System.out.println("SEND " + Protocol.hex(bytes)); }
            public void state(String message) { System.out.println("STATE " + message); }
        });
        BufferedReader reader = new BufferedReader(new InputStreamReader(System.in, "UTF-8"));
        String line;
        while ((line = reader.readLine()) != null) {
            String[] parts = line.split(" ", 3);
            try {
                switch (parts[0]) {
                    case "S":
                        session.start(Protocol.score(parts[2]), Integer.parseInt(parts[1]), 0);
                        break;
                    case "E":
                        Protocol.Score score = Protocol.score(line.substring(2));
                        System.out.println("RECORDS " + score.id + " " + Protocol.hex(score.records));
                        break;
                    case "N": session.notify(Protocol.unhex(parts[2]), Long.parseLong(parts[1])); break;
                    case "T": session.tick(Long.parseLong(parts[1])); break;
                    case "X": session.cancel(Long.parseLong(parts[1])); break;
                    case "D": session.disconnect(); break;
                    case "W": session.transportWritten(); break;
                    case "I":
                        System.out.println("IDENTITY " + Protocol.selectedTarget(parts[1], parts[2]));
                        break;
                    case "Q": System.out.println("END"); System.out.flush(); return;
                    default: throw new IllegalArgumentException("HOST_COMMAND");
                }
            } catch (RuntimeException error) {
                System.out.println("ERROR " + error.getMessage());
            }
            System.out.println("END"); System.out.flush();
        }
    }
}
