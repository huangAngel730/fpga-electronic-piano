// Test-only exact GW5A LUT1/MUX2/mux2 logic; LF normalized.
// Vendor source identity is in R08_HOLD_PREP/VENDOR_MODEL.json.
primitive mux2 (O, I0, I1, S);
output O;
input I0, I1, S;
table
// I0  I1  S     O
   0   ?   0  :  0 ;
   1   ?   0  :  1 ;
   x   ?   0  :  x ;
   ?   0   1  :  0 ;
   ?   1   1  :  1 ;
   ?   x   1  :  x ;
   0   0   x  :  0 ;
   0   1   x  :  x ;
   1   0   x  :  x ;
   1   1   x  :  1 ;
   ?   x   x  :  x ;
   x   ?   x  :  x ;
endtable
endprimitive

module MUX2 (O, I0, I1, S0);

input I0,I1;
input S0;
output O;

mux2 mux2_0 (O, I0, I1, S0);

endmodule

module LUT1 (F, I0);

parameter INIT = 2'h0;

input I0;
output F;

MUX2 lut_1 (F, INIT[0], INIT[1], I0);

endmodule
