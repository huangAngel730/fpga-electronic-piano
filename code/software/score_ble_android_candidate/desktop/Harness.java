import org.m3.score.Protocol;
import java.io.*;
public final class Harness {
    public static void main(String[] args) throws Exception {
        Protocol.Session client=new Protocol.Session(new Protocol.Sink() {
            public void send(byte[] b) { System.out.println("SEND "+Protocol.hex(b)); }
            public void state(String s) { System.out.println("STATE "+s); }
        });
        BufferedReader r=new BufferedReader(new InputStreamReader(System.in,"UTF-8")); String line;
        while((line=r.readLine())!=null) {
            String[] p=line.split(" ",3);
            try {
                if(p[0].equals("E")) { Protocol.Score s=Protocol.score(line.substring(2)); System.out.println("RECORDS "+s.id+" "+Protocol.hex(s.records)); }
                else if(p[0].equals("S")) client.start(Protocol.score(p[2]),Integer.parseInt(p[1]),0);
                else if(p[0].equals("N")) client.notify(Protocol.unhex(p[2]),Long.parseLong(p[1]));
                else if(p[0].equals("T")) client.tick(Long.parseLong(p[1]));
                else if(p[0].equals("D")) client.disconnect();
                else if(p[0].equals("W")) client.transportWritten();
                else if(p[0].equals("X")) client.cancel(Long.parseLong(p[1]));
                else if(p[0].equals("Q")) { System.out.println("END"); break; }
                else if(p[0].equals("G")) System.out.println(Protocol.scanGate(p[1].equals("1"),p[2].equals("1")));
                else if(p[0].equals("I")) System.out.println("IDENTITY "+Protocol.selectedTarget(p[1],p[2]));
                else throw new IllegalArgumentException("command");
            } catch(RuntimeException e) { System.out.println("ERROR "+e.getMessage()); }
            System.out.println("END"); System.out.flush();
        }
    }
}
