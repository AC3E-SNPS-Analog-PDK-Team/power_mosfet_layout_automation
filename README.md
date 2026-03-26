# power_mosfet_layout_automation
Layout automation of power mosfets using Open Source tools (JKU IIC Docker used in SSCS Chipathon)

# IMPORTANT
The LVS of the base block is clean in terms of electrical equivalence between schematic and layout. 
The remaining warnings correspond to discrepancies in port naming, since the base GDS do not contain explicitly exported pins with names consistent with the schematic. 

These base GDS were not modified to add ports, because these blocks are used as input for a script that generates a large MOSFET. Incorporating pins into the base layouts would cause massive replication of labels/ports in the final output, making their handling and extraction difficult.
