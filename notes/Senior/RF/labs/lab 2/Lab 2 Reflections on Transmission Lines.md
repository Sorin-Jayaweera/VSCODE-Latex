
In this lab you are going to simulate reflections on transmission lines to predict the types of voltages you would see at drivers, loads and selected points in the middle of a transmission line.

After this lab, you will be able to:

1. Calculate reflection coefficients and voltage distributions on transmission lines.
2. Predict the time scales and shapes of reflection events at the driving point and load of a transmission line
3. Simulate voltages produced at the terminals of a lossless transmission line.
4. Measure transmission line transients in the lab and understand practical features of lab equipment that affect those transients.
5. Understand, visualize and calculate standing wave patterns on a transmission line.
6. Calculate the load impedance that would generate a measured reflection.

Theory Questions

1. RF cables and some connectors for RF systems are described by their “electrical length.” What is electrical length? Imagine that you used a connector to attach BNC cables to an oscilloscope, how would you measure the electrical length of the connector if you were uncertain of the velocity in the cables? (You may search on the internet to find the answer to this question. Just understand what you find and answer in your own words.)

# TODO
For the following questions, note that BNC cables are transmission lines that have a velocity factor of 0.66 and a characteristic impedance of 50 ohms. Note also that function generators almost all have 50 ohms of source impedance.

2. Consider an oscilloscope and function generator connected as shown in Figure 1 (the box in the figure represents two separate instruments). Calculate the voltage waveforms you expect to see at channels 1, 2 and 3 after Gen Out drives a 1V step onto the transmission line for the terminations listed below. You must deliver a waveform for channels 1, 2 and 3 (possibly overlaid on one another, as if you had measured them on an oscilloscope) as an answer for each scenario.  
      
    Note: This is a lot of math. You may be able to save yourself time with code and/or AI tools. You can generate the plots however you want and you do not have to use AI, but you may be able to save time by writing out what the waveforms should look like, and then asking an AI chatbot to generate the figures for you. You may have even better luck asking an AI chatbot to write code to generate the figures. To be clear, you may NOT use AI to directly calculate or generate code that calculates what the waveforms should be—but you may do the calculations yourself (by hand or writing your own code), then use AI to write code that purely generates plots of the shape you specified. You will still be responsible for the accuracy of your figures (you have to make sure the AI tool correctly interprets what you give it). Up to you! But the intent of this exercise is to learn about time delay and reflections, not spending a long time drawing.

3. An open circuit
4. 50 ohms.
5. A short circuit
6. 22 ohms
7. 200 ohms


![[Pasted image 20260911175527.png]]



## 3

1. Consider an oscilloscope and function generator connected as shown in Figure 2. Calculate the voltage waveforms you expect to see at oscilloscope channels 1, 2 and 3 after gen out drives a 1V step onto the line for the values of shunt and termination resistors listed below. You must deliver a drawn waveform for channels 1, 2 and 3 (possibly overlaid on one another) as an answer for each scenario.

2. 50 ohm shunt and 50 ohm termination 🡨 hint: think about energy conservation
3. 50 ohm shunt and 200 ohm termination 🡨 don’t solve this exactly because it’s a longwinded pain, a general discussion of what happens at the first few reflections and the point to which the line voltage converges is OK.
4. Short shunt and open termination


![[Pasted image 20260911175629.png]]




## 4
1. Finally, consider an oscilloscope and function generator connected as shown in Figure 3. Assume the termination is a 22-ohm resistor and the generator is driving a sinusoid.

2. What VSWR do you expect on the transmission line?
3. If you wanted to sweep the frequency of the input sinusoid to observe the maxima and minima of a standing wave at channel 2, what frequency would you start at and what frequency would you end at? Note this function generator maxes out at 20MHz.
4. Provide a sketch of the expected amplitude of the sinusoidal voltage at channel 2 vs. frequency for the frequencies between the values you found in part b.


![[Pasted image 20260911175700.png]]




## Lab Instructions

1. Use lossless transmission line elements to simulate the scenarios that you calculated waveforms for in the theory section. Compare your simulation and calculations.
2. Build these scenarios from the theory section in the RF lab and record measured voltages at the oscilloscope terminals. Compare your simulation, calculations and theory.
3. In the lab, you will find a “mystery load” (Figure 4). Use your test setup from the previous problems to measure the reflection of the mystery load (e.g., use it as the termination in Figure 1). You don’t need to use the exact test setups from the previous portions of the lab; you just need to be able to calculate the reflection off of this load from your measurements. Calculate the reflection, then determine the impedance that would give you that reflection. Finally, determine the circuit that gives you that impedance (it’s two components).

![[Pasted image 20260911175722.png]]



1. Here are a bunch of useful hints:

2. Don’t forget about the “out-term” setting on function generators. It should be set to Hi-Z. If it is set to “50 Ohm”, then your measurements will appear to be off by a factor of 2.
3. When you make a resistive or short termination, don’t put it at the end of another length of transmission line. (For reasons we’ll go over soon, that will mess up your measurement.) Use BNC tee connectors and BNC-banana connectors to create a short/resistor that attaches right onto the oscilloscope channel..
4. The expectation in this class is that you can make simulations, calculations and theory match well, and that any deviations between them are **_quantitatively_** explained. (e.g., “the connector is 1cm long and velocity in it is different than the transmission line, which accounts for the extra 2cm of length extracted from the waveform” is better than “these don’t match because we didn’t account for the connectors.”)
5. Achieving these quantitative descriptions may require you to perform a process called parasitic extraction, where you add parasitic elements to your simulation and adjust them until it matches your measurements. A little parasitic inductance (approx. nH) in series with grounded elements is often all you need. This is especially important for short terminations. You may also need to adjust the lengths of the transmission lines in your simulation to agree with your measurements, as the cable lengths are inaccurate by a few inches.
6. You will need to include loss in your simulated transmission line models for the scenario in Figure 3. These links will help:  
    [http://ltwiki.org/index.php?title=O_Lossy_Transmission_Line](http://ltwiki.org/index.php?title=O_Lossy_Transmission_Line)  
    [https://electronics.stackexchange.com/questions/323647/ltspice-how-to-model-a-tline](https://electronics.stackexchange.com/questions/323647/ltspice-how-to-model-a-tline)
7. We have a rig to help you build out your BNC measurements, thanks E4 students! See below. This rig cleans up your measurements a lot by reducing strain on the connectors. It’s already set up with the cable lengths you need! Don’t disconnect the wrapped up cables in the back! If you do, you get to grab a tape measure and lay a bunch of cables out in the hallway outside the RF lab at night, then measure out the right lengths of cables to rebuild the rig, which is exactly what Prof. Donahue did this summer before classes started!)

![[Pasted image 20260911175740.png]]