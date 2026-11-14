"""Rookie name tables and the deterministic name allocator (``names_v`` 1+).

Generated rookies used to draw from a 36 x 45 pool, so a long dynasty met the same first names
over and over. From ``names_v`` 1 a rookie's full name is a pure function of
``(seed, season, slot)``: slot ``k`` of the game's whole name sequence is a bijection into the
first x last grid, so no full name can repeat in a save across any number of draft classes, and
a first name comes back only once every ``len(FIRST_V1)`` rookies. The tables are frozen once
shipped: a save made under ``names_v`` 1 regenerates exactly these names, so only ever *append*
a new version (``FIRST_V2`` ...), never edit these tuples.

Saves from before (``names_v`` 0) keep the original tables in ``game_dynasty`` untouched.
"""

from __future__ import annotations

from typing import Collection

from modules.sim.rng import WorldRng

NAMES_VERSION = 1
CLASS_STRIDE = 256  # name slots reserved per season (a class is never larger)
FALLBACK_TRIES = 8

FIRST_V1 = tuple(dict.fromkeys("""
Aaron Abel Abraham Adam Adrian Ahmad Aiden Alan Albert Alec Alejandro Alex Alexander Alfonso Alonzo Amari Amir Anders Andre Andres Andrew Angel Anthony Antoine Anton Antonio Archer Ari Arlo Armando Arthur Asa Ashton Atlas Augustus Austin Avery Axel
Barrett Beau Beckett Ben Benedict Benjamin Bennett Bernard Billy Blaine Blake Bo Bobby Boone Brad Braden Bradley Brandon Brantley Braxton Brayden Brendan Brennan Brent Brett Brian Brice Brock Brody Bronson Bruce Bryan Bryant Bryce Bryson Byron
Cade Caden Caleb Callum Calvin Camden Cameron Camilo Carl Carlos Carlton Carson Carter Casey Cassius Cedric Chance Chandler Charles Charlie Chester Chris Christian Christopher Clarence Clark Clay Clayton Clifford Clint Clyde Cody Colby Cole Colin Collin Colt Colton Connor Conrad Cooper Corbin Cordell Corey Cornell Cory Craig Cruz Curtis Cyrus
Dakota Dale Dallas Dalton Damian Damon Dane Daniel Danny Dante Darian Darius Darnell Darren Darrell Darryl Dashawn David Davion Dawson Dax Dean Deandre Declan Dedrick Deion Delano Dell Demarcus Demetrius Denzel Derek Derrick Desmond Devin Devon Dewayne Dexter Diego Dillon Dominic Dominick Donovan Dorian Douglas Drake Drew Duane Dustin Dwayne Dylan
Easton Eddie Edgar Edmund Eduardo Edwin Eli Elias Elijah Elliot Ellis Elmer Elton Emanuel Emerson Emery Emilio Emmanuel Emmett Enrique Enzo Eric Erik Ernest Esteban Ethan Eugene Evan Everett Ezekiel Ezra
Fabian Felix Fernando Finley Finn Fletcher Floyd Forrest Francis Francisco Frank Franklin Frederick Gabe Gabriel Garrett Gary Gavin Gene Gerald Gerardo Gideon Gilbert Giovanni Glenn Gordon Grady Graham Grant Gregory Griffin Grayson Gunnar Gus Guy
Hakeem Hank Hans Harlan Harold Harper Harrison Harvey Hassan Hayden Heath Hector Henry Herbert Hiram Holden Homer Hosea Houston Howard Hudson Hugh Hugo Hunter
Ian Ibrahim Idris Ignacio Imani Ira Isaac Isaiah Ishmael Israel Ivan Izaiah
Jabari Jace Jack Jackson Jacob Jaden Jadon Jaheim Jahlil Jaiden Jair Jakob Jaleel Jamal Jamar James Jameson Jamie Jared Jarell Jarvis Jason Jasper Javon Jax Jaxon Jay Jayce Jayden Jaylon Jaylen Jaylin Jean Jeff Jeffrey Jeremiah Jeremy Jermaine Jerome Jerry Jesse Jesus Jett Joaquin Joe Joel Joey Johan John Johnny Jon Jonah Jonas Jonathan Jordy Jose Joseph Josiah Josue Jovan Juan Judah Jude Julian Julius Junior Justin
Kade Kai Kaleb Kameron Kamari Kareem Karl Kasen Kashawn Kayden Keegan Keenan Keith Kellen Kelvin Ken Kendrick Kenneth Kent Kenyon Kevin Khalil Kian Kieran Kirk Knox Kristian Kurt Kyle Kyler Kylan
Lamar Lance Landon Lane Larry Lars Lawrence Lazarus Leandro Lee Leif Leland Lennox Leo Leon Leonard Leonidas Leroy Levi Lewis Liam Lincoln Lionel Lloyd Logan Lonnie Lorenzo Louis Lucas Lucian Luis Luka Luke Luther
Mack Maddox Magnus Malachi Malcolm Malik Manny Manuel Marc Marcel Marco Marcos Marion Mario Marlon Marquis Marshall Martin Marvin Mason Mateo Matt Matthew Maurice Maverick Max Maxwell Mekhi Melvin Memphis Micah Michael Miguel Mike Miles Milo Mitchell Mohamed Monte Morgan Moses Muhammad Murphy Myles
Nash Nasir Nate Nathan Nathaniel Neal Ned Neil Nelson Nestor Nicholas Nico Nikolai Noah Noel Nolan Norman Nyles
Oakley Oliver Omar Omari Orlando Oscar Otis Otto Owen
Pablo Palmer Parker Patrick Paul Paxton Pedro Percy Perry Peter Phelan Philip Phoenix Pierce Porter Prescott Preston
Quentin Quincy Quinn Rafael Ralph Ramon Randall Randy Raphael Rashad Rashawn Raul Ray Raymond Reed Reese Reggie Reid Remy Rene Rex Rhett Ricardo Richard Rick Rico Ricky Riley River Robbie Robert Roberto Robin Rocco Rodney Rodrigo Roger Roland Roman Ronald Ronan Ronnie Rory Roscoe Ross Rowan Roy Ruben Rudy Russell Ryan Ryder Rylan
Salvador Sam Samir Samuel Santiago Saul Sawyer Scott Sean Sebastian Sergio Seth Shane Shawn Sheldon Shiloh Sidney Silas Simeon Simon Skylar Solomon Spencer Stanley Stefan Stephen Sterling Steve Stuart Sullivan Sylas
Tad Talon Tanner Tariq Tate Taylor Terrance Terrell Terry Thaddeus Theo Theodore Thomas Tim Timothy Titus Tobias Toby Todd Tom Tomas Tony Travis Trent Trevor Trey Tristan Troy Truman Tucker Tyler Tyrell Tyrone Tyson
Ulises Uriah Valentin Van Vaughn Vernon Victor Vince Vincent Wade Walker Wallace Walter Warren Waylon Wayne Wesley Weston Whit Wilbur Will William Willie Wilson Winston Wolfgang Woodrow Wyatt
Xander Xavier Yadiel Yusuf Zachary Zane Zavier Zayden Zeke Zion
Akeem Alvin Amos Aldo Bastian Bishop Boyd Brooks Cael Cairo Cannon Cayden Chip Cormac Dario Davis Dino Eamon Eben Efrain Fitz Franco Gage Garth Gio Hamilton Hollis Ike Jonny Kenji Kolton Lachlan Luca Maceo Nevin Nils Orion Pax Quade Ramsey Reuben Rufus Shea Stone Teague Tobin Ulric Vance Wells York Zeus
Haruto Kenta Daichi Hiroshi Kaito Jun Wei Jin Hao Minh Tuan Dae Joon Sung Raj Arjun Dev Rohan Vikram Kabir Anil Sanjay Tavita Sione Mika Manu Kalani Keanu Makoa Noa Lokelani Siaosi Tevita Viliami Penitani Ofa Folau Isi Junior Pita Mosese Sefa Fetu Lio Alofa Lemuel Kofi Kwame Kwesi Emeka Chidi Obinna Tunde Segun Ayo Jelani Sekou Mamadou Ousmane Idrissa Babatunde Chukwu Ikenna Nnamdi Uche Zuri Tau Dmitri Sasha Pavel Anatoly Viktor Lukas Matej Tomasz Jakub Marek Stellan Soren Bjorn Gunther Dieter Lorcan Seamus Fergus Callan Ronan Ruairi Cian Donal
""".split()))

LAST_V1 = tuple(dict.fromkeys("""
Abbott Abernathy Acevedo Adair Addison Adeyemi Aguilar Ainsley Akers Albright Aldridge Alford Allard Almonte Alvarado Amato Ames Amos Andrade Appleton Archer Arden Armstrong Arnett Arroyo Ashby Ashford Atwood Aubrey Avila Ayers
Babcock Bachman Baez Bagley Bailey Baines Baird Bakshi Baldwin Ballard Banks Barlow Barnett Barrera Barrow Bartlett Barton Bastian Bauer Baxter Beal Beard Beasley Beaumont Becker Bell Bellamy Benavides Benedict Bennett Benson Bentley Berg Bergman Bernal Berry Best Bianchi Bishop Bjornson Blackburn Blackwell Blaine Blair Blanchard Blevins Bloom Blount Bolden Bolton Bond Bonner Booker Boone Booth Borden Bosworth Bowden Bowen Boyd Boyer Bradshaw Brandt Bravo Breeden Brennan Brewer Bridges Briggs Brinkley Britt Brock Brooks Broussard Brower Browning Brunson Bryce Buchanan Buckley Bui Bullock Burgess Burke Burnett Burris Burrows Burton Bustamante Butler Byrd
Cabrera Cade Cagle Cahill Caldwell Calhoun Callahan Calloway Camacho Cameron Campos Cannon Cano Cantrell Cardenas Carew Carlisle Carmody Carpenter Carrillo Carroll Carson Carver Casey Cash Castaneda Castellano Castro Cavanaugh Chacon Chambers Chandler Chaney Chapman Charles Chavez Cheatham Childs Chin Christensen Church Clancy Clayton Clemons Cleveland Clifton Cobb Coburn Coffey Colbert Coleman Collier Colon Combs Conley Connelly Conover Conrad Contreras Conway Cooke Corbett Corcoran Cordero Corliss Cortez Costa Cotton Coughlin Coulter Courtney Cowan Cox Crabtree Craddock Craig Crane Crawley Creed Crenshaw Crespo Crockett Crosby Crowder Cruz Cullen Cummings Cunningham Curran Currie Curry Curtis Cyr
Dacosta Dalton Daly Damron Dandridge Daniels Danner Darby Davenport Dawkins Deacon Dean Decker Dehaan Deleon Delgado Dempsey Denny Dent Deshields Devlin Dewitt Diaz Dickey Dillard Dillon Dinkins Dobbs Dodson Doherty Dolan Dominguez Donahue Donnelly Dorsey Douglass Downey Doyle Drake Drummond Dube Duffy Dugan Dunbar Duncan Dunlap Dupree Durand Durham Dwyer Dyer
Eads Eagan Earl Eastman Eaton Eberhardt Echols Eddy Edmonds Edwards Egan Eklund Elam Eldridge Elias Elkins Elliott Ellsworth Emery Engel English Enriquez Erdman Erickson Esparza Espinoza Estes Estrada Etheridge Eubanks Evers Ewing
Fabian Fagan Fairchild Falk Farley Farmer Farrell Faulk Faulkner Felix Fenton Ferrara Ferrell Fields Figueroa Finch Finnegan Fischer Fisk Fitch Fitzgerald Flanagan Fleming Flowers Floyd Flynn Foley Ford Foreman Foster Fowler Fox Frady Franco Frazier Freeman Fried Frye Fuentes Fulton Furman
Gaines Galindo Gallagher Gallegos Galloway Galvan Gamble Gannon Garcia Gardner Garner Garrison Gaskill Gaston Gates Gentry George Gerard Gibbons Gibbs Gilbert Gill Gilliam Gillespie Gilmore Gladney Glass Glover Godfrey Goff Goldberg Gomez Gonzales Goodwin Gordon Gorman Goss Grady Graham Granger Grant Grayson Greer Gregory Griffith Grimes Grissom Gross Grove Guerra Guerrero Gunn Gupta Gustafson Gutierrez Guthrie Guzman Gwynn
Haas Haddad Hagan Haines Halliday Halloran Hamilton Hammond Hampton Hancock Haney Hanlon Hanna Hansen Hardin Hargrove Harlan Harmon Harper Harrell Harrington Hartley Harvey Hasan Hatcher Hawkins Hayden Hayes Haynes Heath Hebert Heller Helms Hendrix Henley Hensley Herman Hernandez Herrera Hess Hewitt Hickey Hicks Higgins Hightower Hildebrand Hines Hinton Hodge Hoffman Hogan Holbrook Holcomb Holden Holiday Holland Hollis Holt Hooper Hopkins Horne Horton Houston Howell Hubbard Huerta Huff Hughes Hull Humphrey Hunt Hurley Hutchins Hyde
Ibarra Idowu Iglesias Ikeda Imhoff Irwin Isaacs Ishikawa Ivey Izquierdo
Jackman Jacobs Jaeger Jacoby Jaramillo Jarrett Jasper Jeffries Jenkins Jensen Jerome Jessup Jimenez Joiner Joyce Juarez Judd Julian
Kahale Kaiser Kane Kapoor Karlsson Kavanagh Kearney Keating Keller Kemp Kendall Kenney Kerr Key Keys Khan Kilgore Kimball Kincaid Kinney Kirby Kirkland Klein Knapp Knight Koch Kowalski Kramer Krause Kruger Kuhn Kwon
Labelle Lacey Lafleur Laird Lambert Lancaster Landry Lang Langley Lanier Lara Larkin Larsen Latham Lattimore Lavigne Leach Leal Leblanc Ledbetter Lemon Leonard Levine Lewandowski Lindsey Lister Little Livingston Lockhart Lombardi Longoria Lopez Lovett Lowery Lucero Lucas Luna Lund Lyman Lynch Lyons
Macias Mackey Maddox Madrigal Magee Maguire Mahoney Maier Maldonado Malone Maloney Mancini Mangum Manning Marcus Marin Marlow Marrero Marsh Marston Mata Mathis Matos Maxwell Mayfield Maynard McAllister McBride McCall McCarthy McClain McCoy McCray McDaniel McDowell McFadden McGee McGuire McIntyre McKay McKenna McKinney McLean McMahon McNair McNeil Meadows Medina Mejia Melendez Mendez Mercado Meredith Merritt Meyer Michaud Middleton Milburn Miles Millard Mims Mitchum Mize Molina Monk Montero Montez Montoya Moody Moran Morales Morin Morrow Morse Mosley Moss Mueller Muhammad Mullen Muniz Munoz Murdock Murillo Murray Myers
Nadeau Nagel Nakamura Nance Napier Navarro Neal Neely Nelms Nemeth Newell Newsome Newton Nguyen Nichols Nieves Nobles Noel Norris Norwood Novak Noyes Nunez Nwosu
Oberg Obrien Ochoa Odell Odom Ogden Ogletree Okafor Oliveira Olmstead Olsen Oneal Orr Ortega Ortiz Osborne Osgood Otero Overton Owens Oyelaran
Pace Pacheco Padilla Pagan Pak Palmer Paredes Parham Parrish Patel Patton Payne Peck Pedersen Pelletier Pena Pennington Perdue Perez Perkins Perrin Petersen Pettigrew Pham Phelps Pickett Pierce Pinkney Pittman Plummer Poe Pollard Pope Portis Poole Pratt Prentice Presley Pruitt Puckett Pugh Purcell
Quade Quick Quigley Quinones Quintero
Rader Raines Rainey Ramirez Ramos Rand Randolph Rangel Rasmussen Ratliff Rawlings Raymond Redding Redmond Reece Reeder Regan Reid Renfro Reyes Reynolds Rhodes Rice Richter Ricks Riddle Rigby Riggs Riordan Rios Ritter Rivas Roach Robbins Roberson Robles Rocha Rodriguez Roe Rojas Roldan Romero Rooney Rosales Rosario Ross Roth Rowan Rowe Roy Rudd Ruiz Rush Russo Rutledge Ryan
Saenz Salas Salazar Saldana Salinas Salter Samuels Sanchez Sandoval Sands Sanford Santana Santos Sapp Sargent Saunders Savage Sawyer Saxon Scanlon Schaefer Schmidt Schneider Schroeder Schultz Schwartz Scott Seals Sears Sellers Serrano Sexton Shaffer Shah Shannon Sharp Shaw Shea Shelton Shepard Sheridan Sherman Shields Shipley Shultz Sibley Siegel Silva Simmons Simon Simpson Sims Singh Singleton Skaggs Skinner Slater Slocum Small Snider Solis Solomon Somers Soto Spalding Spangler Spears Spence Spivey Stafford Stallworth Stanton Staples Stark Steele Stein Stephens Sterling Stevenson Stewart Stinson Stokes Stout Strand Strickland Strong Stuart Sturgis Sugden Sullivan Summers Swain Swan Sweeney Swift Sykes
Tafoya Talbot Tanaka Tapia Tatum Teague Tejada Temple Terrell Tessier Thao Thatcher Tillman Tobin Todd Toledo Tolliver Tomlin Torres Townsend Tran Travis Treadway Trejo Tripp Trujillo Tucker Tuttle Tyree
Ulloa Umana Unger Upchurch Urban Uribe Usher Utley
Valdez Valencia Valentine Valenzuela Vance Vang Varela Vargas Vasquez Vega Velasquez Velez Ventura Vera Vickers Villanueva Villarreal Vincent Vo Voss
Wade Wagner Wagoner Waldron Wallace Walls Walsh Walters Walton Ward Warner Warren Waters Watkins Watts Weaver Webb Weiss Welch Wells Wendt Wesley West Westbrook Whalen Wheeler Whitfield Whitley Wiggins Wilder Wiley Wilkerson Willard Williamson Willis Winfield Winters Wise Witt Wolfe Womack Woodard Woodruff Woods Worley Wray Wyatt Wynn
Yamamoto Yancey Yang Yarbrough Yoder York Young Yu Yun
Zamora Zapata Zavala Zeller Zhang Zielinski Zuniga
Adebayo Adekunle Afolabi Agyeman Akinola Amadi Anokye Appiah Asante Boateng Bankole Chukwuma Dlamini Diallo Eze Fofana Gyamfi Ibekwe Kamara Keita Mensah Nkemelu Nwachukwu Ogunbanjo Okonkwo Onyeama Osagie Owusu Sesay Traore Tshabalala Umeh
Aiona Alapati Faleolo Fonoti Havili Kauhane Leota Liufau Maiava Moala Pauga Tuiasosopo Taumoepeau Tupou Vaifale Vaipulu
Andersson Bergstrom Dahl Eriksson Halvorsen Lindqvist Nygaard Petrov Romanov Sokolov Volkov Zelenko Kovacs Horvat Novotny Dvorak Nowak Wisniewski Janssen Visser Dekker Brouwer
Aoki Fujita Hayashi Inoue Kimura Matsuda Mori Nishida Okada Saito Sakamoto Takeda Tamura Watanabe Yoshida Cho Chung Han Hwang Jang Kang Lim Moon Oh Park Seo Shin Song Chan Chow Liang Liu Ng Wong Wu Xu Zhou Bhatt Chopra Desai Iyer Joshi Kulkarni Menon Nair Rao Reddy Sharma Verma
Castellanos Cisneros Duarte Escobar Fajardo Gallardo Guevara Ibanez Leyva Lozano Macedo Naranjo Olivares Palacios Quezada Rivero Segura Tovar Urbina Zamudio
Barone Cannella Capello DeLuca Esposito Ferraro Gallo Greco Lombardo Marino Pagano Rinaldi Sorrentino Tedesco Vitale
Brannigan Calhoun Donahoe Fallon Gilroy Keohane Mulcahy Nolan Oakley Quill Rafferty Sheehan Tierney Whelan
""".split()))


_STREAM = "gnames"


def _perm(seed: int, which: int, n: int) -> list[int]:
    return [int(i) for i in WorldRng(seed).stream(0, _STREAM, which).permutation(n)]


_CACHE: dict[int, tuple[list[int], list[int]]] = {}


def _perms(seed: int) -> tuple[list[int], list[int]]:
    got = _CACHE.get(seed)
    if got is None:
        if len(_CACHE) > 32:
            _CACHE.clear()
        got = _CACHE[seed] = (_perm(seed, 0, len(FIRST_V1)), _perm(seed, 1, len(LAST_V1)))
    return got


def name_at(seed: int, k: int) -> str:
    """The ``k``-th name of the game's sequence. Injective in ``k`` for ``k < len(FIRST_V1) * len(LAST_V1)``,
    and consecutive ``k`` never share a first name (so a class never repeats one)."""

    nf, nl = len(FIRST_V1), len(LAST_V1)
    pf, pl = _perms(seed)
    q, r = divmod(k, nf)
    return f"{FIRST_V1[pf[r]]} {LAST_V1[pl[(q + r * 37) % nl]]}"


def rookie_name(seed: int, season: int, slot: int, blocked: Collection[str] = ()) -> str:
    """A rookie's name: a pure function of ``(seed, season, slot)``, skipping any name already worn by a player in the pool
    (``blocked``: real players of season 1 and every veteran), by moving to a reserved fallback region of the same bijection."""

    base = max(0, season) * CLASS_STRIDE + slot
    name = name_at(seed, base)
    half = len(FIRST_V1) * len(LAST_V1) // 2
    for attempt in range(FALLBACK_TRIES):
        if name not in blocked:
            return name
        name = name_at(seed, half + base * FALLBACK_TRIES + attempt)
    return name


__all__ = ["NAMES_VERSION", "FIRST_V1", "LAST_V1", "name_at", "rookie_name"]
