# Send your DD-214's layout

The DD-214 layout reader could not read your form. To fit the reader to it, we need to
know where things sit on your page, but not what your page says. These steps make two
files on your Mac that hold that geometry and nothing else. You look them over, then send
them.

## Prerequisites

1. Have the repository cloned on your Mac, with `uv` installed.
2. Have your DD-214 as a PDF.

## Steps

1. In the repository's root folder, run:

	```bash
	git checkout main && git pull
	```

	Expected: Git says it is on branch `main`, and the pull ends with no error.

2. Run:

	```bash
	uv sync
	```

	Expected: the command ends with no error.

3. Run this command. Put the path to your DD-214 in place of `<file>.pdf`, and keep the
	quotes:

	```bash
	uv run dd214kw inspect-layout "<file>.pdf" -o layout.txt --png layout.png
	```

	Expected: within a few seconds it prints "Wrote layout.txt and layout.png." and a
	reminder to look the files over. It does not print your file name.

	If it says the PDF has no usable text layer, the scan has no text in it. Run
	`brew install tesseract poppler` and `uv sync --extra ocr`, then run the command
	again with `--ocr` at the end.

4. Open `layout.txt` in a text editor. Expected: the first line says "geometry only;
	contains no text from your document". Every line after the header holds only these:
	- words of ours: `source`, `page`, `label`, `missing`, `line`, `run`, `rule`, `block`,
	`cell`, `status`, `bbox`, `reread`, `crop`, `zoom`, `accepted`, `refused` and the like;
	- ids of ours, such as `L4a`, `L12c`, `B4a` and `B12c`;
	- numbers with one decimal place, which are positions on the page, and small counts;
	- shape codes, such as `A5` (five letters) or `D8` (eight digits).

	A `reread` line says that a cell of block 12 was cut out of the page image and read
	again: the box it was cut at, in the image's pixels, how far it was magnified, the shape
	of what came back, and whether that reading was used. It holds no character of the
	cell.

	Search the file for your last name, your SSN and your home town. Expected: none of
	them is found.

5. Open `layout.png`. Expected: only green and blue outlined boxes, grey filled boxes,
	orange lines, and short tags such as `L4a` or `B4a`. No part of your scan shows.

6. Send `layout.txt` and `layout.png` in the chat. Do not send the PDF.

To learn what each line of `layout.txt` means, see
[Sharing your DD-214 layout safely](../README.md#sharing-your-dd-214-layout-safely) in the
README.
